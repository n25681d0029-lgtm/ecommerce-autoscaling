import hashlib
import os
import time

from flask import Blueprint, g, jsonify, render_template, request
from sqlalchemy import select, text

from . import REQUEST_COUNTER
from .db import db_backend
from .instance_info import get_instance_info, load_average, uptime_seconds
from .models import Product

bp = Blueprint("system", __name__)


@bp.route("/health")
def health():
    """Load Balancer gọi định kỳ. Trả 200 khi ứng dụng và CSDL đều hoạt động."""
    try:
        g.db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    body = {"status": "ok" if db_ok else "db_error", "instance": get_instance_info()["instance_id"]}
    return jsonify(body), (200 if db_ok else 503)


@bp.route("/system")
def system():
    """Trang minh họa: request này do instance nào xử lý."""
    info = get_instance_info()
    return render_template("system.html", info=info, uptime=uptime_seconds(), load=load_average(),
                           cpus=os.cpu_count(), pid=os.getpid(), requests=REQUEST_COUNTER["count"],
                           backend=db_backend())


@bp.route("/system/live")
def live():
    """Trang demo: trình duyệt gọi /api/whoami liên tục và đếm số request mỗi instance trả lời."""
    return render_template("live.html")


@bp.route("/api/whoami")
def whoami():
    info = get_instance_info()
    resp = jsonify(instance_id=info["instance_id"], az=info["availability_zone"], pid=os.getpid(),
                   uptime=uptime_seconds(), load=load_average())
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/api/products")
def api_products():
    rows = g.db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.id)).all()
    return jsonify([{"id": p.id, "sku": p.sku, "name": p.name, "price": p.price, "stock": p.stock} for p in rows])


@bp.route("/api/heavy")
def heavy():
    """MÔ PHỎNG tác vụ nặng CPU (vd. tạo ảnh thumbnail, tính gợi ý sản phẩm).

    Chỉ dùng cho kiểm thử tải để tạo mức CPU đủ cao kích hoạt Auto Scaling.
    Tham số ms: thời gian tính toán mong muốn, giới hạn 10–500 ms.
    """
    ms = max(10, min(request.args.get("ms", 100, type=int) or 100, 500))
    end = time.perf_counter() + ms / 1000
    h = hashlib.sha256(b"seed")
    rounds = 0
    while time.perf_counter() < end:
        for _ in range(200):
            h = hashlib.sha256(h.digest())
        rounds += 200
    return jsonify(instance=get_instance_info()["instance_id"], ms=ms, rounds=rounds)
