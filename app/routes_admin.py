import csv
import io
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from . import catalog
from .images import ImageError, process_upload
from .migrate import image_key
from .models import MAX_PHOTOS, ORDER_STATUSES, Category, Order, OrderItem, Product, ProductPhoto
from .storage import StoreError, get_stores
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
    live = Product.deleted_at.is_(None)
    stats = {
        "orders": db.scalar(select(func.count(Order.id))) or 0,
        "revenue": db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != CANCELLED)) or 0,
        "products": db.scalar(select(func.count(Product.id)).where(live)) or 0,
        "low_stock": db.scalar(select(func.count(Product.id)).where(live, Product.stock < 10)) or 0,
    }
    paid = Order.status != CANCELLED
    since_today = datetime.combine(datetime.utcnow().date(), datetime.min.time())
    stats["today"] = db.scalar(select(func.count(Order.id)).where(Order.created_at >= since_today)) or 0
    stats["pending"] = db.scalar(select(func.count(Order.id)).where(Order.status.in_(["Mới", "Đã xác nhận"]))) or 0
    n_paid = db.scalar(select(func.count(Order.id)).where(paid)) or 0
    stats["avg"] = int(stats["revenue"]) // n_paid if n_paid else 0
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
    low = db.scalars(select(Product).where(live, Product.stock < 10).order_by(Product.stock).limit(8)).all()
    return render_template("admin/dashboard.html", stats=stats, recent=recent, by_instance=by_instance,
                           daily=daily, top=top, low=low)


def _sync_after_edit() -> None:
    """Đẩy thay đổi lên kho dùng chung ngay để máy khác thấy; lỗi thì báo và để đồng bộ nền thử lại."""
    err = catalog.try_sync(g.db)
    if err:
        flash(f"Đã lưu trên máy này nhưng chưa đồng bộ được lên {catalog.status()['store']}: {err}. "
              "Hệ thống sẽ tự thử lại.", "warning")


def _live_product(pid: int) -> Product:
    p = g.db.get(Product, pid)
    if p is None or p.deleted_at is not None:
        abort(404)
    return p


@bp.route("/products")
@admin_required
def products():
    q = request.args.get("q", "").strip()
    cat = request.args.get("cat", "")
    view = request.args.get("view", "")
    stmt = select(Product).where(Product.deleted_at.is_(None)).order_by(Product.id)
    if q:
        stmt = stmt.where(or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%")))
    cats = g.db.scalars(select(Category).order_by(Category.id)).all()
    if cat:
        stmt = stmt.where(Product.category_id == next((c.id for c in cats if c.slug == cat), -1))
    views = {"low": ("Sắp hết (< 10)", Product.stock < 10), "out": ("Hết hàng", Product.stock <= 0),
             "hidden": ("Đang ẩn", Product.is_active.is_(False)), "nophoto": ("Chưa có ảnh", ~Product.photos.any())}
    if view in views:
        stmt = stmt.where(views[view][1])
    items = g.db.scalars(stmt).all()
    return render_template("admin/products.html", items=items, q=q, cat=cat, view=view, cats=cats,
                           views={k: v[0] for k, v in views.items()}, restock_level=RESTOCK_LEVEL,
                           sync=catalog.status())


@bp.route("/products/sync", methods=["POST"])
@admin_required
def sync_now():
    try:
        r = catalog.sync(g.db, force=True)
        flash(f"Đã đồng bộ với {catalog.status()['store']}: nhận {r['applied']} thay đổi từ nơi khác"
              f"{', đã cập nhật catalog.json' if r['pushed'] else ''}.", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Đồng bộ lỗi: {exc}", "danger")
    return redirect(url_for("admin.products"))


@bp.route("/products/restock", methods=["POST"])
@admin_required
def restock():
    """Đưa tồn kho mọi sản phẩm lên tối thiểu RESTOCK_LEVEL (tiện khi kiểm thử tải làm cạn kho)."""
    n = g.db.execute(update(Product).where(Product.stock < RESTOCK_LEVEL, Product.deleted_at.is_(None))
                     .values(stock=RESTOCK_LEVEL, updated_at=catalog.now())).rowcount
    g.db.commit()
    _sync_after_edit()
    flash(f"Đã bổ sung tồn kho cho {n} sản phẩm (tối thiểu {RESTOCK_LEVEL}).", "success")
    return redirect(url_for("admin.products"))


@bp.route("/products/<int:pid>/delete", methods=["POST"])
@admin_required
def product_delete(pid: int):
    """Xóa mềm: sản phẩm biến mất khỏi cửa hàng và trang quản trị, nhưng đơn hàng cũ vẫn giữ nguyên.

    Dòng trong CSDL được giữ làm "bia mộ" để đồng bộ báo cho các máy khác xóa theo.
    """
    p = _live_product(pid)
    name = p.name
    catalog.mark_deleted(p)
    g.db.commit()
    _sync_after_edit()
    flash(f"Đã xóa sản phẩm “{name}”.", "success")
    return redirect(url_for("admin.products"))


def _store_uploads(files) -> list[str]:
    """Kiểm tra, nén và đưa ảnh vào kho dùng chung. Trả về danh sách tên file (mã băm)."""
    primary, local = get_stores()
    keys = []
    for fs in files:
        blob, _ctype = process_upload(fs.read())
        key = image_key(blob)
        primary.put_image(key, blob)
        if primary is not local and catalog.mirror_enabled():
            local.put_image(key, blob)  # bản sao trong thư mục catalog/ để đưa lên git
        if catalog.state["primary_images"] is not None:
            catalog.state["primary_images"].add(key)
        if key not in keys:
            keys.append(key)
    return keys


@bp.route("/products/new", methods=["GET", "POST"])
@bp.route("/products/<int:pid>", methods=["GET", "POST"])
@admin_required
def product_form(pid: int | None = None):
    db = g.db
    p = _live_product(pid) if pid else None
    cats = db.scalars(select(Category).order_by(Category.id)).all()
    ctx = dict(cats=cats, max_photos=MAX_PHOTOS)
    if request.method == "POST":
        f = request.form
        try:
            data = dict(sku=f["sku"].strip(), name=f["name"].strip(), category_id=int(f["category_id"]),
                        price=int(f["price"]), stock=int(f["stock"]), description=f.get("description", ""),
                        hue=int(f.get("hue") or 210), is_active=bool(f.get("is_active")))
        except (KeyError, ValueError):
            flash("Dữ liệu không hợp lệ.", "danger")
            return render_template("admin/product_form.html", p=p, **ctx), 400

        # Ảnh: giữ ảnh cũ trừ ảnh bị đánh dấu xóa, đưa ảnh được chọn làm ảnh chính lên đầu, thêm ảnh mới vào cuối
        existing = [ph.key for ph in p.photos] if p else []
        removed = set(f.getlist("remove_photo"))
        keep = [k for k in existing if k not in removed]
        cover = f.get("cover")
        if cover in keep:
            keep.remove(cover)
            keep.insert(0, cover)
        uploads = [fs for fs in request.files.getlist("images") if fs and fs.filename]

        error = None
        if not data["sku"] or not data["name"] or len(data["sku"]) > 40 or len(data["name"]) > 160:
            error = "SKU (tối đa 40 ký tự) và tên sản phẩm (tối đa 160 ký tự) không được để trống."
        elif "~del" in data["sku"]:
            error = "SKU không được chứa “~del”."
        elif data["price"] < 0 or data["stock"] < 0:
            error = "Giá và tồn kho không được âm."
        elif not 0 <= data["hue"] <= 359:
            error = "Màu ảnh minh họa phải trong khoảng 0–359."
        elif db.get(Category, data["category_id"]) is None:
            error = "Danh mục không tồn tại."
        elif len(keep) + len(uploads) > MAX_PHOTOS:
            error = f"Mỗi sản phẩm tối đa {MAX_PHOTOS} ảnh (đang có {len(keep)}, chọn thêm {len(uploads)})."
        elif db.scalar(select(Product.id).where(Product.sku == data["sku"], Product.id != (p.id if p else -1))):
            error = f"Mã SKU “{data['sku']}” đã được dùng cho sản phẩm khác."
        new_keys = []
        if not error and uploads:
            try:
                new_keys = _store_uploads(uploads)
            except ImageError as exc:
                error = str(exc)
            except StoreError as exc:
                error = f"Không lưu được ảnh vào kho: {exc}"
        if error:
            flash(error, "danger")
            return render_template("admin/product_form.html", p=p, **ctx), 400

        if p is None:
            p = Product(uid=uuid.uuid4().hex, **data)
            db.add(p)
        else:
            for k, v in data.items():
                setattr(p, k, v)
        keys = list(dict.fromkeys(keep + new_keys))
        if keys != existing:
            p.photos = [ProductPhoto(key=k, position=i) for i, k in enumerate(keys)]
        p.updated_at = catalog.now()
        try:
            db.commit()
        except IntegrityError:  # hai quản trị viên cùng lưu một SKU trong tích tắc
            db.rollback()
            flash(f"Mã SKU “{data['sku']}” đã được dùng cho sản phẩm khác.", "danger")
            return render_template("admin/product_form.html", p=db.get(Product, pid) if pid else None, **ctx), 400
        _sync_after_edit()
        flash("Đã lưu sản phẩm.", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", p=p, **ctx)


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
