import math
import re
import secrets
from datetime import datetime

from flask import (Blueprint, Response, abort, flash, g, redirect, render_template, request, send_file, session,
                   url_for)
from markupsafe import escape
from sqlalchemy import func, or_, select

from .instance_info import get_instance_info
from .models import ORDER_STATUSES, Category, Order, OrderItem, Product
from .orders import CANCELLED, NEW, cancel_order
from .storage import IMAGE_CACHE, StoreError, get_stores

MEDIA_KEY_RE = re.compile(r"^[0-9a-f]{16,64}\.jpg$")

bp = Blueprint("shop", __name__)
PAGE_SIZE = 12
MAX_QTY = 10  # số lượng tối đa của một sản phẩm trong giỏ
PHONE_RE = re.compile(r"^[0-9+ ]{9,15}$")

# Hình vẽ nét (line-art) cho ảnh minh họa SVG theo danh mục, tâm ở khoảng (110, 96)
_GLYPHS = {
    "dien-thoai": '<rect x="82" y="42" width="56" height="108" rx="9"/><path d="M102 52h16"/><circle cx="110" cy="138" r="4"/>',
    "laptop": '<rect x="58" y="58" width="104" height="66" rx="4"/><path d="M42 134h136l-8 10H50z"/><path d="M100 139h20"/>',
    "may-tinh-bang": '<rect x="64" y="40" width="92" height="116" rx="8"/><rect x="74" y="52" width="72" height="88" rx="2"/><circle cx="110" cy="148" r="3"/>',
    "am-thanh": '<path d="M66 122v-22a44 44 0 0 1 88 0v22"/><rect x="56" y="112" width="20" height="38" rx="7"/><rect x="144" y="112" width="20" height="38" rx="7"/>',
    "dong-ho": '<path d="M96 40h28l4 22M96 40l-4 22M96 152h28l4-22M96 152l-4-22"/><circle cx="110" cy="96" r="34"/><path d="M110 78v18l12 8"/>',
    "phu-kien": '<path d="M86 58h48v40a24 24 0 0 1-48 0z"/><path d="M98 42v16M122 42v16M110 122v34"/>',
}

PRICE_RANGES = {  # khóa tham số ?price= -> (nhãn, từ, đến)
    "u1": ("Dưới 1 triệu", 0, 1_000_000),
    "1-5": ("1 – 5 triệu", 1_000_000, 5_000_000),
    "5-15": ("5 – 15 triệu", 5_000_000, 15_000_000),
    "o15": ("Trên 15 triệu", 15_000_000, None),
}
SORTS = [("featured", "Nổi bật"), ("new", "Mới nhất"), ("price_asc", "Giá tăng dần"), ("price_desc", "Giá giảm dần")]
RECENT_MAX = 8


def short_price(v: int) -> str:
    """Giá rút gọn cho banner: 150000 -> "150K", 2690000 -> "2,69 TRIỆU"."""
    if v < 1_000_000:
        return f"{v // 1000}K"
    return f"{v / 1_000_000:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " TRIỆU"


def _promo() -> dict:
    """Số liệu thật cho banner trang chủ: giá thấp nhất toàn shop và của từng danh mục (không ghi cứng giá)."""
    rows = g.db.execute(select(Category.slug, Category.name, func.min(Product.price), func.count(Product.id))
                        .join(Product, Product.category_id == Category.id)
                        .where(Product.is_active.is_(True), Product.stock > 0)
                        .group_by(Category.id, Category.slug, Category.name).order_by(Category.id)).all()
    cats = [{"slug": s, "name": n, "from": short_price(lo), "count": c, "glyph": _GLYPHS.get(s, "")}
            for s, n, lo, c in rows]
    return {"from": short_price(min((r[2] for r in rows), default=0)), "cats": cats[:3],
            "total": sum(r[3] for r in rows)}


def page_window(page: int, pages: int, around: int = 2) -> list[int | None]:
    """Danh sách số trang để hiển thị, None là dấu "…": 1 … 4 5 [6] 7 8 … 20."""
    keep = {1, pages} | set(range(max(1, page - around), min(pages, page + around) + 1))
    out, prev = [], 0
    for i in sorted(keep):
        if i - prev > 1:
            out.append(None)
        out.append(i)
        prev = i
    return out


def _remember_view(pid: int) -> None:
    seen = [x for x in session.get("seen", []) if x != pid]
    session["seen"] = ([pid] + seen)[:RECENT_MAX]


def recently_viewed(exclude: int | None = None, limit: int = 6) -> list[Product]:
    ids = [i for i in session.get("seen", []) if i != exclude][:limit]
    if not ids:
        return []
    found = {p.id: p for p in g.db.scalars(select(Product).where(Product.id.in_(ids),
                                                                  Product.is_active.is_(True))).all()}
    return [found[i] for i in ids if i in found]


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
    q = request.args.get("q", "").strip()[:100]
    cat_slug = request.args.get("cat", "")
    sort = request.args.get("sort", "featured")
    sort = sort if sort in dict(SORTS) else "featured"
    price = request.args.get("price", "")
    price = price if price in PRICE_RANGES else ""
    instock = request.args.get("instock") == "1"
    page = max(to_int(request.args.get("page"), 1), 1)

    stmt = select(Product).where(Product.is_active.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Product.name.ilike(like), Product.description.ilike(like), Product.sku.ilike(like)))
    current_cat = None
    if cat_slug:
        current_cat = g.db.scalar(select(Category).where(Category.slug == cat_slug))
        if current_cat:
            stmt = stmt.where(Product.category_id == current_cat.id)
    if price:
        _, lo, hi = PRICE_RANGES[price]
        stmt = stmt.where(Product.price >= lo)
        if hi is not None:
            stmt = stmt.where(Product.price < hi)
    if instock:
        stmt = stmt.where(Product.stock > 0)
    # "featured": trộn đều các danh mục bằng một hoán vị cố định của id (chạy được trên SQLite và MySQL)
    order_by = {"price_asc": Product.price.asc(), "price_desc": Product.price.desc(),
                "new": Product.id.desc()}.get(sort, (Product.id * 7) % 37)
    total = g.db.scalar(select(func.count()).select_from(stmt.subquery()))
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(page, pages)
    products = g.db.scalars(stmt.order_by(order_by, Product.id).offset((page - 1) * PAGE_SIZE)
                            .limit(PAGE_SIZE)).all()
    filters = {"q": q or None, "cat": current_cat.slug if current_cat else None,
               "sort": None if sort == "featured" else sort, "price": price or None,
               "instock": "1" if instock else None}
    landing = not (q or current_cat or price or instock) and page == 1
    return render_template("index.html", products=products, q=q, current_cat=current_cat, sort=sort, sorts=SORTS,
                           price=price, price_ranges=PRICE_RANGES, instock=instock, page=page, pages=pages,
                           window=page_window(page, pages), total=total, filters=filters, landing=landing,
                           recent=recently_viewed() if landing else [], promo=_promo() if landing else None)


@bp.route("/product/<int:pid>")
def product_detail(pid: int):
    p = g.db.get(Product, pid)
    if not p or not p.is_active:
        abort(404)
    related = g.db.scalars(select(Product).where(Product.category_id == p.category_id, Product.id != p.id,
                                                 Product.is_active.is_(True))
                           .order_by((Product.id * 7) % 37).limit(4)).all()
    recent = recently_viewed(exclude=p.id, limit=4)
    _remember_view(p.id)
    in_cart = _cart().get(str(p.id), 0)
    return render_template("product.html", p=p, related=related, recent=recent, in_cart=in_cart, max_qty=MAX_QTY)


@bp.route("/img/product/<int:pid>.svg")
def product_image(pid: int):
    """Ảnh minh họa khi sản phẩm chưa có ảnh thật: nhãn giấy, khối màu theo `hue`, hình vẽ nét theo danh mục."""
    p = g.db.get(Product, pid)
    if not p:
        abort(404)
    glyph = _GLYPHS.get(p.category.slug, '<rect x="70" y="56" width="80" height="80" rx="4"/>')
    h = p.hue % 360
    sku = escape(p.sku.split("~del")[0])
    cat = escape(p.category.name.upper())
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 200">
<defs><pattern id="d" width="7" height="7" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.1" fill="#16130f" opacity=".16"/></pattern></defs>
<rect width="220" height="200" fill="#efe8da"/>
<circle cx="146" cy="84" r="58" fill="hsl({h},48%,62%)"/>
<rect width="220" height="200" fill="url(#d)"/>
<g fill="none" stroke="#16130f" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" transform="translate(-6 4)">{glyph}</g>
<rect x="10" y="10" width="200" height="180" fill="none" stroke="#16130f" stroke-width="1.5"/>
<path d="M10 166h200" stroke="#16130f" stroke-width="1.5"/>
<text x="18" y="183" font-family="JetBrains Mono,Consolas,monospace" font-size="11" font-weight="700" fill="#16130f">{sku}</text>
<text x="202" y="183" font-family="JetBrains Mono,Consolas,monospace" font-size="8.5" fill="#16130f" text-anchor="end" opacity=".7">{cat}</text>
</svg>'''
    return Response(svg, mimetype="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


@bp.route("/media/<key>")
def media(key: str):
    """Ảnh sản phẩm từ kho dùng chung.

    Trên AWS trình duyệt tải ảnh thẳng từ CloudFront (không qua route này). Route này dùng khi chạy cục bộ
    (ảnh nằm trong thư mục catalog/images) hoặc khi chưa cấu hình MEDIA_BASE_URL.
    Tên file là mã băm nội dung nên được lưu đệm vĩnh viễn.
    """
    if not MEDIA_KEY_RE.match(key):
        abort(404)
    primary, local = get_stores()
    if local.has_image(key):
        r = send_file(local.image_path(key), mimetype="image/jpeg", max_age=31536000, conditional=True)
    else:
        if primary is local:
            abort(404)
        try:
            r = Response(primary.get_image(key), mimetype="image/jpeg")
        except KeyError:
            abort(404)
        except StoreError:
            abort(503)
    r.headers["Cache-Control"] = IMAGE_CACHE
    r.headers["X-Content-Type-Options"] = "nosniff"
    return r


@bp.app_template_global()
def media_url(key: str) -> str:
    primary, _ = get_stores()
    return primary.public_url(key) or url_for("shop.media", key=key)


@bp.app_template_global()
def product_img_url(p: Product) -> str:
    """Ảnh chính của sản phẩm; chưa có ảnh thì dùng ảnh minh họa SVG theo màu."""
    key = p.cover_key
    if key:
        return media_url(key)
    # ?v= đổi khi quản trị viên sửa sản phẩm (màu, SKU) để trình duyệt không dùng ảnh minh họa cũ đã lưu đệm
    return url_for("shop.product_image", pid=p.id, v=int(p.updated_at.timestamp()) if p.updated_at else None)


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
    if request.form.get("buy_now"):
        return redirect(url_for("shop.checkout"))
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


def _summary() -> dict:
    """Tóm tắt giỏ hàng (không sửa giỏ) để hiện cạnh form đặt hàng."""
    cart = _cart()
    ids = [to_int(i) for i in cart]
    found = {p.id: p for p in g.db.scalars(select(Product).where(Product.id.in_(ids))).all()} if ids else {}
    items = [{"p": found[to_int(k)], "qty": q, "subtotal": q * found[to_int(k)].price}
             for k, q in cart.items() if to_int(k) in found and q > 0]
    return {"items": items, "total": sum(i["subtotal"] for i in items)}


@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = _cart()
    if not cart:
        flash("Giỏ hàng đang trống.", "warning")
        return redirect(url_for("shop.index"))
    if request.method == "GET":
        return render_template("checkout.html", summary=_summary())

    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    address = request.form.get("address", "").strip()
    if not (name and phone and address):
        flash("Vui lòng nhập đủ họ tên, số điện thoại và địa chỉ.", "danger")
        return render_template("checkout.html", summary=_summary()), 400
    # Giới hạn theo độ dài cột trong CSDL (MySQL strict mode báo lỗi nếu chuỗi quá dài)
    if not PHONE_RE.match(phone) or len(name) > 120 or len(address) > 255:
        flash("Số điện thoại gồm 9–15 chữ số; họ tên tối đa 120 ký tự, địa chỉ tối đa 255 ký tự.", "danger")
        return render_template("checkout.html", summary=_summary()), 400

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
    steps = [s for s in ORDER_STATUSES if s != CANCELLED]
    step = steps.index(order.status) if order.status in steps else -1
    return render_template("order.html", order=order, can_cancel=order.status == NEW and _owns(order),
                           steps=steps, step=step, units=sum(it.quantity for it in order.items))


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
