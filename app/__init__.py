import os
import secrets

from flask import Flask, g, render_template, session

from .db import SessionLocal, wait_for_db
from .instance_info import get_instance_info

REQUEST_COUNTER = {"count": 0}


def format_vnd(value: int) -> str:
    return f"{value:,.0f}".replace(",", ".") + " ₫"


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    # SECRET_KEY phải GIỐNG NHAU trên mọi instance để cookie phiên (giỏ hàng,
    # đăng nhập) hợp lệ dù Load Balancer chuyển request sang máy nào.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(16)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.jinja_env.filters["vnd"] = format_vnd

    wait_for_db()
    from .seed import init_db
    init_db()

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

    @app.teardown_request
    def _cleanup(exc=None):
        SessionLocal.remove()

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def _error(exc):
        code = getattr(exc, "code", 500) or 500
        if code >= 500:
            SessionLocal.rollback()  # phiên CSDL có thể đang ở trạng thái lỗi
        return render_template("error.html", code=code), code

    @app.context_processor
    def _inject():
        cart = session.get("cart", {})
        return {
            "server": get_instance_info(),
            "cart_count": sum(cart.values()),
            "current_user_name": session.get("user_name"),
            "is_admin": session.get("is_admin", False),
        }

    return app
