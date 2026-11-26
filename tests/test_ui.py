"""Giao diện mới: chống CSRF, bộ lọc, phân trang, vừa xem, mua ngay, lọc trong trang quản trị."""
import re

import pytest
from conftest import login, place_order

from app.models import Product
from app.routes_shop import page_window


@pytest.fixture()
def csrf_on(app):
    app.config["CSRF_ENABLED"] = True
    yield
    app.config["CSRF_ENABLED"] = False


def token_from(html: str) -> str:
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def test_csrf_blocks_forged_post(client, csrf_on):
    r = client.post("/cart/add/1", data={"qty": 1})
    assert r.status_code == 400 and "Phiên làm việc đã hết hạn" in r.get_data(as_text=True)
    with client.session_transaction() as s:
        assert not s.get("cart")

    tok = token_from(client.get("/product/1").get_data(as_text=True))
    assert client.post("/cart/add/1", data={"qty": 1, "csrf_token": tok}).status_code == 302
    assert client.post("/cart/add/1", data={"qty": 1, "csrf_token": "sai"}).status_code == 400
    # Gọi từ JavaScript/công cụ: gửi token qua header
    assert client.post("/cart/add/2", data={"qty": 1}, headers={"X-CSRF-Token": tok}).status_code == 302


def test_every_post_form_has_csrf_field(client):
    login(client)
    place_order(client, pid=1)
    for url in ["/", "/product/1", "/cart", "/login", "/register", "/track", "/admin/products",
                "/admin/products/1", "/admin/orders", "/account"]:
        html = client.get(url).get_data(as_text=True)
        for form in re.findall(r"<form[^>]*method=\"post\"[^>]*>.*?</form>", html, re.S):
            assert 'name="csrf_token"' in form, (url, form[:120])


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Frame-Options"] == "SAMEORIGIN" and r.headers["X-Content-Type-Options"] == "nosniff"


def test_price_and_stock_filters(client, db):
    body = client.get("/?price=u1").get_data(as_text=True)
    assert "Cáp USB-C" in body and "Laptop gaming" not in body
    body = client.get("/?price=o15&cat=laptop").get_data(as_text=True)
    assert "Laptop gaming Raptor" in body and "Laptop sinh viên" not in body

    p = db.query(Product).filter_by(sku="PK-003").one()
    p.stock = 0
    db.commit()
    assert "Cáp USB-C to USB-C" in client.get("/?q=cáp").get_data(as_text=True)
    assert "Cáp USB-C to USB-C" not in client.get("/?q=cáp&instock=1").get_data(as_text=True)
    assert "Hết hàng" in client.get("/?q=cáp").get_data(as_text=True)  # mộc "Hết hàng" trên thẻ
    assert client.get("/?price=khong-hop-le&sort=abc").status_code == 200


def test_search_by_sku_and_pagination(client):
    assert "Laptop Aero 14" in client.get("/?q=LT-001").get_data(as_text=True)
    body = client.get("/?page=999").get_data(as_text=True)  # trang vượt quá -> về trang cuối
    assert 'aria-current="page">3<' in body
    assert page_window(1, 1) == [1]
    assert page_window(6, 20) == [1, None, 4, 5, 6, 7, 8, None, 20]
    assert page_window(2, 5) == [1, 2, 3, 4, 5]


def test_recently_viewed(client):
    client.get("/product/3")
    client.get("/product/7")
    body = client.get("/").get_data(as_text=True)
    assert "Bạn vừa xem" in body and "Orbit X Pro" in body
    body = client.get("/product/3").get_data(as_text=True)
    assert "Bạn vừa xem" in body and "Laptop Aero 14" in body


def test_buy_now_goes_to_checkout(client):
    r = client.post("/cart/add/1", data={"qty": 2, "buy_now": "1"})
    assert r.headers["Location"].endswith("/checkout")
    body = client.get("/checkout").get_data(as_text=True)
    assert "Đơn của bạn" in body and "Điện thoại Nova A15" in body


def test_order_page_shows_progress(client):
    code = place_order(client)
    body = client.get(f"/order/{code}").get_data(as_text=True)
    assert 'class="now">Mới<' in body and "Hóa đơn bán lẻ" in body


def test_logout_by_post(client):
    login(client)
    assert client.post("/logout").status_code == 302
    assert "/login" in client.get("/account").headers["Location"]


def test_admin_product_filters(client, db):
    login(client)
    body = client.get("/admin/products?cat=am-thanh").get_data(as_text=True)
    assert "Tai nghe không dây" in body and "Laptop Aero" not in body
    db.get(Product, 5).stock = 3
    db.get(Product, 6).is_active = False
    db.commit()
    body = client.get("/admin/products?view=low").get_data(as_text=True)
    assert "Lumo C3" in body and "Nova A15" not in body
    assert "Flexa Z" in client.get("/admin/products?view=hidden").get_data(as_text=True)
    assert "Nova A15" in client.get("/admin/products?view=nophoto").get_data(as_text=True)


def test_placeholder_svg_is_escaped(client, db):
    p = db.get(Product, 1)
    p.sku = 'X<script>"'
    db.commit()
    svg = client.get("/img/product/1.svg").get_data(as_text=True)
    assert "<script>" not in svg and "&lt;script&gt;" in svg
