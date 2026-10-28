from conftest import login, place_order

from app.models import Order, Product


def stock(db, pid):
    db.expire_all()
    return db.get(Product, pid).stock


def test_home_and_filters(client):
    assert client.get("/").status_code == 200
    r = client.get("/?cat=laptop&sort=price_asc")
    assert r.status_code == 200 and "Laptop" in r.get_data(as_text=True)
    assert "Tai nghe" in client.get("/?q=tai nghe").get_data(as_text=True)


def test_invalid_page_param_does_not_crash(client):
    assert client.get("/?page=abc").status_code == 200
    assert client.get("/?page=-5").status_code == 200


def test_product_detail_and_404(client, db):
    assert client.get("/product/1").status_code == 200
    assert client.get("/product/9999").status_code == 404
    db.get(Product, 1).is_active = False
    db.commit()
    assert client.get("/product/1").status_code == 404


def test_product_image_svg(client):
    r = client.get("/img/product/1.svg")
    assert r.status_code == 200 and r.mimetype == "image/svg+xml"


def test_cart_add_update_remove(client):
    client.post("/cart/add/1", data={"qty": 2})
    client.post("/cart/add/2", data={"qty": "khong-phai-so"})  # giá trị lỗi -> mặc định 1
    with client.session_transaction() as s:
        assert s["cart"] == {"1": 2, "2": 1}
    client.post("/cart/update", data={"qty_1": "5", "qty_2": "0", "qty_99": "3"})
    with client.session_transaction() as s:
        assert s["cart"] == {"1": 5}  # qty 0 -> bỏ; id không có trong giỏ -> bỏ qua
    client.post("/cart/remove/1")
    with client.session_transaction() as s:
        assert s["cart"] == {}


def test_cart_qty_capped_at_max_and_stock(client, db):
    client.post("/cart/add/1", data={"qty": 50})
    with client.session_transaction() as s:
        assert s["cart"]["1"] == 10
    db.get(Product, 12).stock = 3
    db.commit()
    client.post("/cart/add/12", data={"qty": 10})
    with client.session_transaction() as s:
        assert s["cart"]["12"] == 3


def test_cannot_add_out_of_stock_or_inactive(client, db):
    db.get(Product, 1).stock = 0
    db.get(Product, 2).is_active = False
    db.commit()
    client.post("/cart/add/1")
    assert client.post("/cart/add/2").status_code == 404
    with client.session_transaction() as s:
        assert s.get("cart", {}) == {}


def test_cart_page_drops_products_hidden_after_adding(client, db):
    client.post("/cart/add/1")
    client.post("/cart/add/2")
    db.get(Product, 2).is_active = False
    db.commit()
    body = client.get("/cart").get_data(as_text=True)
    assert "ngừng bán" in body
    with client.session_transaction() as s:
        assert s["cart"] == {"1": 1}


def test_checkout_creates_order_and_decrements_stock(client, db):
    before = stock(db, 1)
    code = place_order(client, pid=1, qty=2)
    assert code
    o = db.query(Order).filter_by(code=code).one()
    assert o.total == 2 * db.get(Product, 1).price
    assert o.status == "Mới" and o.served_by.startswith("local-")
    assert stock(db, 1) == before - 2
    with client.session_transaction() as s:
        assert s["cart"] == {}
    assert client.get(f"/order/{code}").status_code == 200


def test_checkout_rejects_invalid_phone_and_missing_fields(client):
    client.post("/cart/add/1")
    r = client.post("/checkout", data={"name": "A", "phone": "abc", "address": "X"})
    assert r.status_code == 400
    r = client.post("/checkout", data={"name": "", "phone": "0900000000", "address": "X"})
    assert r.status_code == 400


def test_checkout_insufficient_stock(client, db):
    client.post("/cart/add/12", data={"qty": 3})
    db.get(Product, 12).stock = 1  # có người khác mua trước
    db.commit()
    r = client.post("/checkout", data={"name": "A", "phone": "0900000000", "address": "X"})
    assert r.headers["Location"].endswith("/cart")
    assert stock(db, 12) == 1
    assert db.query(Order).count() == 0


def test_checkout_empty_cart_redirects(client):
    r = client.get("/checkout")
    assert r.status_code == 302


def test_guest_can_cancel_own_new_order_and_stock_restored(client, db):
    before = stock(db, 1)
    code = place_order(client, pid=1, qty=3)
    assert "Hủy đơn hàng" in client.get(f"/order/{code}").get_data(as_text=True)
    client.post(f"/order/{code}/cancel")
    db.expire_all()
    assert db.query(Order).filter_by(code=code).one().status == "Đã hủy"
    assert stock(db, 1) == before
    # Hủy lần nữa không cộng kho thêm
    client.post(f"/order/{code}/cancel")
    assert stock(db, 1) == before


def test_stranger_cannot_cancel_order(app, client):
    code = place_order(client)
    other = app.test_client()
    assert other.post(f"/order/{code}/cancel").status_code == 403
    assert "Hủy đơn hàng" not in other.get(f"/order/{code}").get_data(as_text=True)


def test_cannot_cancel_after_shop_confirmed(client, db):
    code = place_order(client)
    o = db.query(Order).filter_by(code=code).one()
    o.status = "Đã xác nhận"
    db.commit()
    client.post(f"/order/{code}/cancel")
    db.expire_all()
    assert db.query(Order).filter_by(code=code).one().status == "Đã xác nhận"


def test_logged_in_user_sees_and_can_cancel_own_orders(app, client):
    client.post("/register", data={"email": "an@test.vn", "full_name": "An", "password": "matkhau1"})
    code = place_order(client)
    assert code in client.get("/my-orders").get_data(as_text=True)
    # Đăng nhập trên trình duyệt khác (không có cookie my_codes) vẫn hủy được vì đơn thuộc tài khoản
    other = app.test_client()
    login(other, "an@test.vn", "matkhau1")
    assert other.post(f"/order/{code}/cancel").status_code == 302


def test_track_redirects_to_order(client):
    code = place_order(client)
    r = client.post("/track", data={"code": code.lower()})
    assert r.headers["Location"].endswith(f"/order/{code}")
    assert client.get("/order/KHONGCO").status_code == 404
