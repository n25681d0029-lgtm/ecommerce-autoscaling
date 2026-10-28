from conftest import login, place_order

from app.models import Order, Product


def test_admin_pages_require_admin(client):
    for url in ["/admin/", "/admin/products", "/admin/orders", "/admin/orders.csv"]:
        assert "/login" in client.get(url).headers["Location"]
    client.post("/register", data={"email": "kh@test.vn", "full_name": "KH", "password": "matkhau1"})
    assert "/login" in client.get("/admin/").headers["Location"]


def test_dashboard_stats(client):
    place_order(client, pid=1, qty=2)
    login(client)
    body = client.get("/admin/").get_data(as_text=True)
    assert "Doanh thu 7 ngày" in body and "Bán chạy nhất" in body
    assert "Điện thoại Nova A15" in body  # sản phẩm vừa bán xuất hiện trong bảng bán chạy


def test_create_product_and_validation(client, db):
    login(client)
    data = {"sku": "NEW-1", "name": "Sản phẩm mới", "category_id": "1", "price": "1000", "stock": "5",
            "hue": "100", "is_active": "on"}
    assert client.post("/admin/products/new", data=data).status_code == 302
    assert db.query(Product).filter_by(sku="NEW-1").one().price == 1000

    r = client.post("/admin/products/new", data=data)  # trùng SKU
    assert r.status_code == 400 and "đã được dùng" in r.get_data(as_text=True)
    r = client.post("/admin/products/new", data=dict(data, sku="NEW-2", price="-1"))
    assert r.status_code == 400
    r = client.post("/admin/products/new", data=dict(data, sku="NEW-3", price="abc"))
    assert r.status_code == 400
    r = client.post("/admin/products/new", data=dict(data, sku="NEW-4", category_id="999"))
    assert r.status_code == 400
    assert db.query(Product).filter(Product.sku.like("NEW-%")).count() == 1


def test_edit_product(client, db):
    login(client)
    data = {"sku": "DT-001", "name": "Tên mới", "category_id": "1", "price": "123", "stock": "7", "hue": "10"}
    client.post("/admin/products/1", data=data)
    db.expire_all()
    p = db.get(Product, 1)
    assert (p.name, p.price, p.is_active) == ("Tên mới", 123, False)
    assert client.get("/admin/products/9999").status_code == 404


def test_product_search(client):
    login(client)
    body = client.get("/admin/products?q=LT-00").get_data(as_text=True)
    assert "Laptop" in body and "Điện thoại Nova" not in body


def test_restock(client, db):
    login(client)
    db.get(Product, 1).stock = 0
    db.commit()
    client.post("/admin/products/restock")
    db.expire_all()
    assert db.get(Product, 1).stock == 100
    assert db.query(Product).filter(Product.stock < 100).count() == 0


def test_cancel_by_admin_restores_stock_and_is_final(app, client, db):
    shopper = app.test_client()
    before = db.get(Product, 1).stock
    code = place_order(shopper, pid=1, qty=4)
    oid = db.query(Order).filter_by(code=code).one().id
    login(client)
    client.post(f"/admin/orders/{oid}/status", data={"status": "Đang giao"})
    client.post(f"/admin/orders/{oid}/status", data={"status": "Đã hủy"})
    db.expire_all()
    assert db.get(Order, oid).status == "Đã hủy"
    assert db.get(Product, 1).stock == before
    client.post(f"/admin/orders/{oid}/status", data={"status": "Mới"})
    db.expire_all()
    assert db.get(Order, oid).status == "Đã hủy"
    assert db.get(Product, 1).stock == before


def test_order_filters_and_csv(app, client, db):
    shopper = app.test_client()
    c1 = place_order(shopper, pid=1, phone="0911111111")
    c2 = place_order(shopper, pid=2, phone="0922222222")
    o2 = db.query(Order).filter_by(code=c2).one()
    o2.status = "Hoàn thành"
    db.commit()
    login(client)
    body = client.get("/admin/orders?status=Hoàn thành").get_data(as_text=True)
    assert c2 in body and c1 not in body
    body = client.get("/admin/orders?q=0911111111").get_data(as_text=True)
    assert c1 in body and c2 not in body
    r = client.get("/admin/orders.csv")
    text = r.get_data(as_text=True)
    assert r.mimetype == "text/csv" and text.startswith("﻿code,")
    assert c1 in text and c2 in text
