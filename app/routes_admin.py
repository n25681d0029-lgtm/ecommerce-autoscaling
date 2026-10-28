import csv
import io
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .models import ORDER_STATUSES, Category, Order, OrderItem, Product
from .orders import CANCELLED, cancel_order

bp = Blueprint("admin", __name__, url_prefix="/admin")
RESTOCK_LEVEL = 100


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


@bp.route("/")
@admin_required
def dashboard():
    db = g.db
    stats = {
        "orders": db.scalar(select(func.count(Order.id))) or 0,
        "revenue": db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != CANCELLED)) or 0,
        "products": db.scalar(select(func.count(Product.id))) or 0,
        "low_stock": db.scalar(select(func.count(Product.id)).where(Product.stock < 10)) or 0,
    }
    recent = db.scalars(select(Order).order_by(Order.id.desc()).limit(10)).all()
    # Số đơn hàng do từng instance xử lý -> minh chứng tải được chia đều
    by_instance = db.execute(select(Order.served_by, func.count(Order.id))
                             .group_by(Order.served_by).order_by(func.count(Order.id).desc())).all()

    # Doanh thu 7 ngày gần nhất (theo ngày UTC). func.date chạy được trên cả SQLite và MySQL.
    today = datetime.utcnow().date()
    since = today - timedelta(days=6)
    day = func.date(Order.created_at)
    rows = db.execute(select(day, func.count(Order.id), func.coalesce(func.sum(Order.total), 0))
                      .where(Order.created_at >= datetime.combine(since, datetime.min.time()),
                             Order.status != CANCELLED)
                      .group_by(day)).all()
    per_day = {str(d): (n, int(rev)) for d, n, rev in rows}
    daily = []
    for i in range(7):
        d = since + timedelta(days=i)
        n, rev = per_day.get(d.isoformat(), (0, 0))
        daily.append({"label": d.strftime("%d/%m"), "orders": n, "revenue": rev})
    peak = max((x["revenue"] for x in daily), default=0) or 1
    for x in daily:
        x["pct"] = round(x["revenue"] * 100 / peak)

    sold = func.sum(OrderItem.quantity)
    top = db.execute(select(OrderItem.product_name, sold, func.sum(OrderItem.quantity * OrderItem.price))
                     .join(Order).where(Order.status != CANCELLED)
                     .group_by(OrderItem.product_name).order_by(sold.desc()).limit(5)).all()
    low = db.scalars(select(Product).where(Product.stock < 10).order_by(Product.stock).limit(8)).all()
    return render_template("admin/dashboard.html", stats=stats, recent=recent, by_instance=by_instance,
                           daily=daily, top=top, low=low)


@bp.route("/products")
@admin_required
def products():
    q = request.args.get("q", "").strip()
    stmt = select(Product).order_by(Product.id)
    if q:
        stmt = stmt.where(or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%")))
    items = g.db.scalars(stmt).all()
    return render_template("admin/products.html", items=items, q=q, restock_level=RESTOCK_LEVEL)


@bp.route("/products/restock", methods=["POST"])
@admin_required
def restock():
    """Đưa tồn kho mọi sản phẩm lên tối thiểu RESTOCK_LEVEL (tiện khi kiểm thử tải làm cạn kho)."""
    n = g.db.execute(update(Product).where(Product.stock < RESTOCK_LEVEL).values(stock=RESTOCK_LEVEL)).rowcount
    g.db.commit()
    flash(f"Đã bổ sung tồn kho cho {n} sản phẩm (tối thiểu {RESTOCK_LEVEL}).", "success")
    return redirect(url_for("admin.products"))


@bp.route("/products/new", methods=["GET", "POST"])
@bp.route("/products/<int:pid>", methods=["GET", "POST"])
@admin_required
def product_form(pid: int | None = None):
    db = g.db
    p = db.get(Product, pid) if pid else None
    if pid and not p:
        abort(404)
    cats = db.scalars(select(Category).order_by(Category.id)).all()
    if request.method == "POST":
        f = request.form
        try:
            data = dict(sku=f["sku"].strip(), name=f["name"].strip(), category_id=int(f["category_id"]),
                        price=int(f["price"]), stock=int(f["stock"]), description=f.get("description", ""),
                        hue=int(f.get("hue") or 210), is_active=bool(f.get("is_active")))
        except (KeyError, ValueError):
            flash("Dữ liệu không hợp lệ.", "danger")
            return render_template("admin/product_form.html", p=p, cats=cats), 400
        error = None
        if not data["sku"] or not data["name"] or len(data["sku"]) > 40 or len(data["name"]) > 160:
            error = "SKU (tối đa 40 ký tự) và tên sản phẩm (tối đa 160 ký tự) không được để trống."
        elif data["price"] < 0 or data["stock"] < 0:
            error = "Giá và tồn kho không được âm."
        elif not 0 <= data["hue"] <= 359:
            error = "Màu ảnh minh họa phải trong khoảng 0–359."
        elif db.get(Category, data["category_id"]) is None:
            error = "Danh mục không tồn tại."
        if error:
            flash(error, "danger")
            return render_template("admin/product_form.html", p=p, cats=cats), 400
        if p is None:
            p = Product(**data)
            db.add(p)
        else:
            for k, v in data.items():
                setattr(p, k, v)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            flash(f"Mã SKU “{data['sku']}” đã được dùng cho sản phẩm khác.", "danger")
            return render_template("admin/product_form.html", p=db.get(Product, pid) if pid else None,
                                   cats=cats), 400
        flash("Đã lưu sản phẩm.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", p=p, cats=cats)


def _filtered_orders():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    stmt = select(Order).order_by(Order.id.desc())
    if status in ORDER_STATUSES:
        stmt = stmt.where(Order.status == status)
    if q:
        stmt = stmt.where(or_(Order.code.ilike(f"%{q}%"), Order.phone.ilike(f"%{q}%"),
                              Order.customer_name.ilike(f"%{q}%")))
    return stmt, status, q


@bp.route("/orders")
@admin_required
def orders():
    stmt, status, q = _filtered_orders()
    items = g.db.scalars(stmt.limit(200)).all()
    counts = dict(g.db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all())
    return render_template("admin/orders.html", items=items, statuses=ORDER_STATUSES, status=status, q=q,
                           counts=counts)


@bp.route("/orders.csv")
@admin_required
def orders_csv():
    """Xuất danh sách đơn (theo bộ lọc hiện tại) ra CSV để đưa vào báo cáo."""
    stmt, _, _ = _filtered_orders()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["code", "created_at_utc", "customer_name", "phone", "address", "total", "status", "served_by"])
    for o in g.db.scalars(stmt).all():
        w.writerow([o.code, o.created_at.strftime("%Y-%m-%d %H:%M:%S"), o.customer_name, o.phone, o.address,
                    o.total, o.status, o.served_by])
    # BOM để Excel nhận đúng tiếng Việt UTF-8
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=orders.csv"})


@bp.route("/orders/<int:oid>/status", methods=["POST"])
@admin_required
def order_status(oid: int):
    o = g.db.get(Order, oid)
    if not o:
        abort(404)
    st = request.form.get("status")
    if st in ORDER_STATUSES and st != o.status:
        if o.status == CANCELLED:
            # Đơn đã hủy đã hoàn kho; mở lại sẽ phải trừ kho lần nữa nên không cho phép
            flash(f"Đơn {o.code} đã hủy, không thể đổi trạng thái.", "warning")
        elif st == CANCELLED:
            cancel_order(g.db, o)
            g.db.commit()
            flash(f"Đã hủy đơn {o.code} và hoàn lại tồn kho.", "success")
        else:
            o.status = st
            g.db.commit()
    return redirect(request.referrer or url_for("admin.orders"))
