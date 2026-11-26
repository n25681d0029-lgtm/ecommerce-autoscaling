"""Đồng bộ sản phẩm giữa các máy.

"Máy khác" được giả lập bằng fresh_machine(): xóa sạch CSDL rồi khởi động lại như một máy mới,
chỉ giữ kho catalog (thư mục catalog/ lấy qua git, hoặc bucket S3 dùng chung).
"""
import io
import json
import os
from datetime import datetime, timedelta

import pytest
from conftest import fresh_machine, login, place_order
from test_images import FORM, make_image, post_form

from app import catalog
from app.models import Order, Product
from app.storage import Conflict, LocalStore, S3Store, reset_stores, set_stores

CATALOG_JSON = os.path.join(os.environ["CATALOG_DIR"], "catalog.json")


def read_catalog():
    with open(CATALOG_JSON, encoding="utf-8") as f:
        return json.load(f)


def test_edit_on_one_machine_visible_on_another(app, client, db):
    login(client)
    post_form(client, "/admin/products/new", FORM, [make_image()])
    post_form(client, "/admin/products/1", dict(FORM, sku="DT-001", name="Nova A15 bản mới", price="4500000"))
    assert any(e.get("sku") == "IMG-1" for e in read_catalog()["products"])

    fresh_machine()  # máy B: CSDL trống, chỉ có thư mục catalog/
    db.expire_all()
    new = db.query(Product).filter_by(sku="IMG-1").one()
    assert len(new.photos) == 1 and new.name == "Sản phẩm có ảnh"
    p1 = db.query(Product).filter_by(sku="DT-001").one()
    assert (p1.name, p1.price) == ("Nova A15 bản mới", 4500000)
    assert db.query(Product).filter(Product.deleted_at.is_(None)).count() == 37  # 36 mẫu + 1, không nhân đôi
    assert "Nova A15 bản mới" in client.get("/").get_data(as_text=True)


def test_delete_product_is_soft_and_propagates(app, client, db):
    code = place_order(app.test_client(), pid=2, qty=1)
    login(client)
    r = client.post("/admin/products/2/delete")
    assert r.status_code == 302
    db.expire_all()
    p = db.get(Product, 2)
    assert p.deleted_at is not None and not p.is_active
    assert client.get("/product/2").status_code == 404
    assert client.get("/admin/products/2").status_code == 404
    assert "DT-002" not in client.get("/admin/products").get_data(as_text=True)
    # Đơn hàng cũ vẫn còn nguyên
    assert db.query(Order).filter_by(code=code).one().items[0].product_name.startswith("Điện thoại Nova A35")
    # SKU được giải phóng để dùng lại
    assert post_form(client, "/admin/products/new", dict(FORM, sku="DT-002")).status_code == 302

    fresh_machine()  # máy khác: sản phẩm mẫu DT-002 cũ phải bị xóa theo, không được "hồi sinh"
    db.expire_all()
    assert db.query(Product).filter_by(uid="sku:DT-002").one().deleted_at is not None
    assert db.query(Product).filter_by(sku="DT-002").one().name == "Sản phẩm có ảnh"


def test_newer_edit_wins(app, db):
    """Hai máy sửa cùng một sản phẩm: bản sửa sau cùng thắng, ở cả CSDL lẫn catalog.json."""
    doc = read_catalog()
    entry = next(e for e in doc["products"] if e["uid"] == "sku:DT-003")
    entry.update(name="Sửa từ máy khác", updated_at=catalog.iso(datetime.utcnow() + timedelta(seconds=5)))
    with open(CATALOG_JSON, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)

    p = db.query(Product).filter_by(uid="sku:DT-003").one()
    p.name, p.updated_at = "Sửa cũ ở máy này", datetime.utcnow()
    db.commit()
    catalog.sync(force=True)
    db.expire_all()
    assert db.query(Product).filter_by(uid="sku:DT-003").one().name == "Sửa từ máy khác"

    p = db.query(Product).filter_by(uid="sku:DT-003").one()
    p.name, p.updated_at = "Sửa mới nhất ở máy này", datetime.utcnow() + timedelta(seconds=10)
    db.commit()
    catalog.sync()
    assert next(e for e in read_catalog()["products"] if e["uid"] == "sku:DT-003")["name"] == "Sửa mới nhất ở máy này"


def test_orders_do_not_overwrite_catalog_stock(app, db):
    before = next(e for e in read_catalog()["products"] if e["uid"] == "sku:DT-001")["stock"]
    place_order(app.test_client(), pid=1, qty=3)
    catalog.sync(force=True)
    assert next(e for e in read_catalog()["products"] if e["uid"] == "sku:DT-001")["stock"] == before
    db.expire_all()
    assert db.get(Product, 1).stock == before - 3  # tồn kho thực tế ở máy này không bị ghi đè


def test_sync_button(client):
    login(client)
    r = client.post("/admin/products/sync")
    assert r.status_code == 302
    assert "Đã đồng bộ" in client.get("/admin/products").get_data(as_text=True)


# ------------------------------------------------------------------ S3 (giả lập, không cần AWS)
class FakeS3:
    """Giả lập các lệnh S3 mà S3Store dùng, kể cả ghi có điều kiện IfMatch/IfNoneMatch."""

    class Err(Exception):
        def __init__(self, code):
            super().__init__(code)
            self.response = {"Error": {"Code": code}}

    def __init__(self):
        self.objects, self.n = {}, 0

    def _etag(self):
        self.n += 1
        return f'"{self.n}"'

    def get_object(self, Bucket, Key, IfNoneMatch=None):
        if Key not in self.objects:
            raise self.Err("NoSuchKey")
        body, etag = self.objects[Key]
        if IfNoneMatch == etag:
            raise self.Err("304")
        return {"Body": io.BytesIO(body), "ETag": etag}

    def put_object(self, Bucket, Key, Body, IfMatch=None, IfNoneMatch=None, **_):
        cur = self.objects.get(Key)
        if (IfNoneMatch == "*" and cur) or (IfMatch and (not cur or cur[1] != IfMatch)):
            raise self.Err("PreconditionFailed")
        self.objects[Key] = (Body, self._etag())
        return {"ETag": self.objects[Key][1]}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise self.Err("404")

    def list_objects_v2(self, Bucket, Prefix, **_):
        return {"Contents": [{"Key": k} for k in self.objects if k.startswith(Prefix)], "IsTruncated": False}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)


@pytest.fixture()
def s3(app):
    fake = FakeS3()
    store = S3Store("test-bucket", public_base_url="https://cdn.example.net", client=fake)
    set_stores(store, LocalStore(os.environ["CATALOG_DIR"]))
    catalog.reset_state()
    yield fake
    reset_stores()


def test_s3_hub_shared_between_aws_and_local(s3, client, db, monkeypatch):
    catalog.sync(force=True)  # bucket trống: dữ liệu ban đầu được đẩy lên từ thư mục catalog/
    assert "catalog.json" in s3.objects

    login(client)
    post_form(client, "/admin/products/new", FORM, [make_image()])
    key = db.query(Product).filter_by(sku="IMG-1").one().photos[0].key
    assert f"images/{key}" in s3.objects  # ảnh lên S3, và có bản sao trong catalog/ để đưa lên git
    assert os.path.exists(os.path.join(os.environ["CATALOG_DIR"], "images", key))
    body = client.get("/").get_data(as_text=True)
    assert f"https://cdn.example.net/images/{key}" in body  # trình duyệt lấy ảnh thẳng từ CloudFront

    # Một EC2 mới (CSDL trống, thư mục mã nguồn không có catalog, không ghi bản sao) vẫn thấy sản phẩm
    import shutil
    shutil.rmtree(os.environ["CATALOG_DIR"])
    monkeypatch.setenv("CATALOG_MIRROR", "0")
    from app.db import Base, SessionLocal, engine
    from app.seed import init_db
    SessionLocal.remove()
    Base.metadata.drop_all(engine)
    catalog.reset_state()
    init_db()
    catalog.sync(force=True)
    db.expire_all()
    assert len(db.query(Product).filter_by(sku="IMG-1").one().photos) == 1


def test_s3_concurrent_write_is_merged(s3, db):
    catalog.sync(force=True)
    store = catalog.get_stores()[0]
    real_put = s3.put_object
    calls = {"n": 0}

    def racing_put(**kw):
        # Lần ghi đầu tiên: máy khác chen vào ghi catalog.json ngay trước mình
        if kw["Key"] == "catalog.json" and calls["n"] == 0:
            calls["n"] += 1
            doc = json.loads(s3.objects["catalog.json"][0])
            e = next(x for x in doc["products"] if x["uid"] == "sku:LT-001")
            e.update(name="Máy khác vừa sửa", updated_at=catalog.iso(datetime.utcnow()))
            s3.objects["catalog.json"] = (json.dumps(doc).encode(), s3._etag())
        return real_put(**kw)

    s3.put_object = racing_put
    p = db.query(Product).filter_by(uid="sku:DT-004").one()
    p.name, p.updated_at = "Máy này vừa sửa", datetime.utcnow()
    db.commit()
    catalog.sync()
    names = {e["uid"]: e.get("name") for e in json.loads(s3.objects["catalog.json"][0])["products"]}
    assert names["sku:DT-004"] == "Máy này vừa sửa" and names["sku:LT-001"] == "Máy khác vừa sửa"
    with pytest.raises(Conflict):
        store.write_catalog({"x": 1}, '"etag-cu"')
