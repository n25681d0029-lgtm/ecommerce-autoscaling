import os
import secrets
import time
from datetime import datetime

from flask import Flask, g, render_template, session

from .db import SessionLocal, wait_for_db
from .images import MAX_UPLOAD_MB
from .instance_info import get_instance_info

REQUEST_COUNTER = {"count": 0}
NAV_TTL = 30
_NAV_CACHE: dict = {"at": -1e9, "rows": []}


def format_vnd(value: int) -> str:
    return f"{value:,.0f}".replace(",", ".") + " ₫"


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    # SECRET_KEY phải GIỐNG NHAU trên mọi instance để cookie phiên (giỏ hàng,
    # đăng nhập) hợp lệ dù Load Balancer chuyển request sang máy nào.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(16)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Giới hạn kích thước request (ảnh sản phẩm tải lên); vượt quá -> lỗi 413
    app.config["MAX_CONTENT_LENGTH"] = (MAX_UPLOAD_MB + 1) * 1024 * 1024
    app.jinja_env.filters["vnd"] = format_vnd

    wait_for_db()
    from .seed import init_db
    init_db()
    # Gộp danh mục sản phẩm với kho dùng chung (S3 hoặc thư mục catalog/) để thấy thay đổi từ máy khác.
    # Lỗi (vd. mất mạng tới S3) không làm website ngừng chạy: lần đồng bộ nền sau sẽ thử lại.
    from . import catalog
    catalog.try_sync(force=True)
    catalog.start_background(float(os.environ.get("SYNC_INTERVAL", "30")))

    from .routes_admin import bp as admin_bp
    from .routes_auth import bp as auth_bp
    from .routes_shop import bp as shop_bp
    from .routes_system import bp as system_bp
    app.register_blueprint(shop_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(system_bp)

    @app.before_request
    def _count():
        REQUEST_COUNTER["count"] += 1
        g.db = SessionLocal()

    from . import security
    security.init_app(app)  # đăng ký SAU _count để g.db luôn có sẵn kể cả khi CSRF báo lỗi

    @app.teardown_request
    def _cleanup(exc=None):
        SessionLocal.remove()

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    @app.errorhandler(500)
    def _error(exc):
        code = getattr(exc, "code", 500) or 500
        if code >= 500:
            SessionLocal.rollback()  # phiên CSDL có thể đang ở trạng thái lỗi
        return render_template("error.html", code=code, csrf=getattr(exc, "description", "") == "csrf"), code

    @app.context_processor
    def _inject():
        cart = session.get("cart", {})
        return {
            "categories_nav": _nav_categories(),
            "server": get_instance_info(),
            "cart_count": sum(cart.values()),
            "current_user_name": session.get("user_name"),
            "is_admin": session.get("is_admin", False),
            "max_upload_mb": MAX_UPLOAD_MB,
            "server_now": datetime.utcnow(),
        }

    def _nav_categories():
        """Danh mục + số sản phẩm cho thanh điều hướng của mọi trang.

        Lưu đệm trong tiến trình NAV_TTL giây để không thêm một truy vấn CSDL cho mỗi request
        (quan trọng khi kiểm thử tải). Lỗi CSDL thì trả danh sách cũ/rỗng để trang lỗi vẫn hiện được.
        """
        now = time.monotonic()
        if now - _NAV_CACHE["at"] < NAV_TTL and not app.config.get("TESTING"):
            return _NAV_CACHE["rows"]
        try:
            from sqlalchemy import func, select

            from .models import Category, Product
            rows = SessionLocal().execute(
                select(Category.slug, Category.name, func.count(Product.id))
                .outerjoin(Product, (Product.category_id == Category.id) & Product.is_active.is_(True))
                .group_by(Category.id, Category.slug, Category.name).order_by(Category.id)).all()
            _NAV_CACHE.update(at=now, rows=[tuple(r) for r in rows])
        except Exception:  # noqa: BLE001
            SessionLocal.rollback()
        return _NAV_CACHE["rows"]

    return app
