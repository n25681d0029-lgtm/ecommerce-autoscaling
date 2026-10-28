import math
import re
import secrets
from datetime import datetime

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_, select

from .instance_info import get_instance_info
from .models import Category, Order, OrderItem, Product
from .orders import NEW, cancel_order

bp = Blueprint("shop", __name__)
PAGE_SIZE = 12
MAX_QTY = 10  # số lượng tối đa của một sản phẩm trong giỏ
PHONE_RE = re.compile(r"^[0-9+ ]{9,15}$")

# Biểu tượng đơn giản cho ảnh minh họa SVG theo danh mục
_GLYPHS = {
    "dien-thoai": '<rect x="78" y="40" width="64" height="120" rx="10" fill="none" stroke="white" stroke-width="6"/><circle cx="110" cy="146" r="5" fill="white"/>',
    "laptop": '<rect x="55" y="55" width="110" height="70" rx="6" fill="none" stroke="white" stroke-width="6"/><rect x="40" y="130" width="140" height="10" rx="4" fill="white"/>',
    "may-tinh-bang": '<rect x="60" y="45" width="100" height="120" rx="10" fill="none" stroke="white" stroke-width="6"/><circle cx="110" cy="152" r="4" fill="white"/>',
    "am-thanh": '<path d="M65 120 v-20 a45 45 0 0 1 90 0 v20" fill="none" stroke="white" stroke-width="6"/><rect x="55" y="110" width="22" height="40" rx="8" fill="white"/><rect x="143" y="110" width="22" height="40" rx="8" fill="white"/>',
    "dong-ho": '<rect x="90" y="30" width="40" height="140" rx="8" fill="white" opacity=".35"/><circle cx="110" cy="100" r="34" fill="none" stroke="white" stroke-width="6"/><path d="M110 82 v18 l12 8" stroke="white" stroke-width="5" fill="none"/>',
    "phu-kien": '<path d="M85 60 h50 v40 a25 25 0 0 1 -50 0z" fill="none" stroke="white" stroke-width="6"/><path d="M98 45 v15 M122 45 v15 M110 125 v35" stroke="white" stroke-width="6"/>',
}


def _cart() -> dict:
    return session.setdefault("cart", {})


def to_int(value, default: int = 0) -> int:
    """Đổi tham số từ form/URL sang số nguyên; giá trị lỗi thì dùng mặc định thay vì báo lỗi 500."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _remember_order(code: str) -> None:
    """Ghi nhớ đơn khách vãng lai vừa đặt (trong cookie phiên) để cho phép họ tự hủy."""
    codes = session.get("my_codes", [])
    session["my_codes"] = (codes + [code])[-20:]


def _owns(order: Order) -> bool:
    uid = session.get("user_id")
    return (uid is not None and order.user_id == uid) or order.code in session.get("my_codes", [])


@bp.route("/")
def index():
    q = request.args.get("q", "").strip()
    cat_slug = request.args.get("cat", "")
    sort = request.args.get("sort", "featured")
    page = max(to_int(request.args.get("page"), 1), 1)

    stmt = select(Product).where(Product.is_active.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.description.ilike(like)))
    current_cat = None
    if cat_slug:
        current_cat = g.db.scalar(select(Category).where(Category.slug == cat_slug))
        if current_cat:
            stmt = stmt.where(Product.category_id == current_cat.id)
    # "featured": trộn đều các danh mục bằng một hoán vị cố định của id (chạy được trên SQLite và MySQL)
    order_by = {"price_asc": Product.price.asc(), "price_desc": Product.price.desc(),
                "new": Product.id.desc()}.get(sort, (Product.id * 7) % 37)
    total = g.db.scalar(select(func.count()).select_from(stmt.subquery()))
    products = g.db.scalars(stmt.order_by(order_by).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)).all()
    categories = g.db.scalars(select(Category).order_by(Category.id)).all()
    return render_template("index.html", products=products, categories=categories, q=q,
                           current_cat=current_cat, sort=sort, page=page,
                           pages=max(1, math.ceil(total / PAGE_SIZE)), total=total)


@bp.route("/product/<int:pid>")
def product_detail(pid: int):
    p = g.db.get(Product, pid)
    if not p or not p.is_active:
        abort(404)
    related = g.db.scalars(select(Product).where(Product.category_id == p.category_id, Product.id != p.id,
                                                 Product.is_active.is_(True)).limit(4)).all()
    return render_template("product.html", p=p, related=related)


@bp.route("/img/product/<int:pid>.svg")
def product_image(pid: int):
    p = g.db.get(Product, pid)
    if not p:
        abort(404)
    glyph = _GLYPHS.get(p.category.slug, "")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 200">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="hsl({p.hue},70%,55%)"/><stop offset="1" stop-color="hsl({(p.hue + 40) % 360},70%,38%)"/>
</linearGradient></defs><rect width="220" height="200" fill="url(#g)"/>{glyph}
<text x="12" y="190" font-family="Arial" font-size="13" fill="white" opacity=".85">{p.sku}</text></svg>'''
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@bp.route("/cart")
def cart():
    cart = _cart()
    items, total = [], 0
    if cart:
        ids = [to_int(i) for i in cart]
        found = {str(p.id): p for p in g.db.scalars(select(Product).where(Product.id.in_(ids))).all()}
        for pid in list(cart):
            p = found.get(pid)
            # Sản phẩm bị ẩn/xóa hoặc hết hàng sau khi khách thêm vào giỏ: bỏ khỏi giỏ và báo cho khách
            if p is None or not p.is_active or p.stock <= 0:
                cart.pop(pid)
                session.modified = True
                if p is not None:
                    flash(f"“{p.name}” đã ngừng bán hoặc hết hàng nên được bỏ khỏi giỏ.", "warning")
                continue
            if cart[pid] > p.stock:
                cart[pid] = p.stock
                session.modified = True
                flash(f"“{p.name}” chỉ còn {p.stock} sản phẩm, đã điều chỉnh số lượng.", "warning")
            qty = cart[pid]
            items.append({"p": p, "qty": qty, "subtotal": qty * p.price})
            total += qty * p.price
    return render_template("cart.html", items=items, total=total)


@bp.route("/cart/add/<int:pid>", methods=["POST"])
def cart_add(pid: int):
    p = g.db.get(Product, pid)
    if not p or not p.is_active:
        abort(404)
    if p.stock <= 0:
        flash(f"“{p.name}” đã hết hàng.", "warning")
        return redirect(request.referrer or url_for("shop.product_detail", pid=pid))
    qty = max(1, min(to_int(request.form.get("qty"), 1), MAX_QTY))
    cart = _cart()
    cart[str(pid)] = min(cart.get(str(pid), 0) + qty, p.stock, MAX_QTY)
    session.modified = True
    flash(f"Đã thêm “{p.name}” vào giỏ hàng.", "success")
    return redirect(request.referrer or url_for("shop.cart"))


@bp.route("/cart/update", methods=["POST"])
def cart_update():
    cart = _cart()
    for key, val in request.form.items():
        if key.startswith("qty_"):
            pid = key[4:]
            if pid not in cart:
                continue
            q = to_int(val, cart[pid])
            if q <= 0:
                cart.pop(pid, None)
            else:
                cart[pid] = min(q, MAX_QTY)
    session.modified = True
    return redirect(url_for("shop.cart"))


@bp.route("/cart/remove/<int:pid>", methods=["POST"])
def cart_remove(pid: int):
    _cart().pop(str(pid), None)
    session.modified = True
    return redirect(url_for("shop.cart"))


@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = _cart()
    if not cart:
        flash("Giỏ hàng đang trống.", "warning")
        return redirect(url_for("shop.index"))
    if request.method == "GET":
        return render_template("checkout.html")

    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    if not (name and phone and address):
        flash("Vui lòng nhập đủ họ tên, số điện thoại và địa chỉ.", "danger")
        return render_template("checkout.html"), 400
    # Giới hạn theo độ dài cột trong CSDL (MySQL strict mode báo lỗi nếu chuỗi quá dài)
    if not PHONE_RE.match(phone) or len(name) > 120 or len(address) > 255:
        flash("Số điện thoại gồm 9–15 chữ số; họ tên tối đa 120 ký tự, địa chỉ tối đa 255 ký tự.", "danger")
        return render_template("checkout.html"), 400

    # Giao dịch: khóa dòng sản phẩm, kiểm tra tồn kho, trừ kho và tạo đơn
    db = g.db
    try:
        ids = [to_int(i) for i in cart]
        products = db.scalars(select(Product).where(Product.id.in_(ids), Product.is_active.is_(True))
                              .with_for_update()).all()
        if len(products) != len(cart):
            db.rollback()
            flash("Một số sản phẩm trong giỏ đã ngừng bán, vui lòng kiểm tra lại giỏ hàng.", "warning")
            return redirect(url_for("shop.cart"))
        total, lines = 0, []
        for p in products:
            qty = cart[str(p.id)]
            if qty <= 0 or qty > p.stock:
                db.rollback()
                flash(f"“{p.name}” chỉ còn {p.stock} sản phẩm.", "danger")
                return redirect(url_for("shop.cart"))
            p.stock -= qty
            total += qty * p.price
            lines.append(OrderItem(product_id=p.id, product_name=p.name, price=p.price, quantity=qty))
        code = datetime.utcnow().strftime("DH%y%m%d") + secrets.token_hex(3).upper()
        order = Order(code=code, user_id=session.get("user_id"), customer_name=name, phone=phone,
                      address=address, total=total, items=lines,
                      served_by=get_instance_info()["instance_id"])
        db.add(order)
        db.commit()
    except Exception:
        db.rollback()
        raise
    session["cart"] = {}
    _remember_order(code)
    return redirect(url_for("shop.order_view", code=code))


@bp.route("/order/<code>")
def order_view(code: str):
    order = g.db.scalar(select(Order).where(Order.code == code))
    if not order:
        abort(404)
    return render_template("order.html", order=order, can_cancel=order.status == NEW and _owns(order))


@bp.route("/order/<code>/cancel", methods=["POST"])
def order_cancel(code: str):
    """Khách tự hủy đơn khi đơn còn ở trạng thái "Mới"; tồn kho được hoàn lại."""
    order = g.db.scalar(select(Order).where(Order.code == code))
    if not order:
        abort(404)
    if not _owns(order):
        abort(403)
    if order.status != NEW:
        flash("Đơn hàng đã được cửa hàng xử lý, không thể tự hủy.", "warning")
    else:
        cancel_order(g.db, order)
        g.db.commit()
        flash("Đã hủy đơn hàng, tồn kho đã được hoàn lại.", "success")
    return redirect(url_for("shop.order_view", code=code))


@bp.route("/track", methods=["GET", "POST"])
def track():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        if not code:
            return redirect(url_for("shop.track"))
        return redirect(url_for("shop.order_view", code=code))
    return render_template("track.html")


@bp.route("/my-orders")
def my_orders():
    uid = session.get("user_id")
    if not uid:
        return redirect(url_for("auth.login", next=url_for("shop.my_orders")))
    orders = g.db.scalars(select(Order).where(Order.user_id == uid).order_by(Order.id.desc())).all()
    return render_template("my_orders.html", orders=orders)
