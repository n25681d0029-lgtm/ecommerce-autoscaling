import io
import os

from conftest import login
from PIL import Image

from app.models import Product

FORM = {"sku": "IMG-1", "name": "Sản phẩm có ảnh", "category_id": "1", "price": "1000", "stock": "5",
        "hue": "100", "is_active": "on"}
CATALOG_IMAGES = os.path.join(os.environ["CATALOG_DIR"], "images")


def make_image(fmt="PNG", size=(1600, 900), mode="RGBA", color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new(mode, size, color + ((128,) if mode == "RGBA" else ())).save(buf, fmt)
    buf.seek(0)
    return buf


def post_form(client, url, data, images=()):
    payload = dict(data)
    if images:
        payload["images"] = [(img, f"anh{i}.png") for i, img in enumerate(images)]
    return client.post(url, data=payload, content_type="multipart/form-data")


def keys_of(db, sku):
    db.expire_all()
    return [ph.key for ph in db.query(Product).filter_by(sku=sku).one().photos]


def test_create_product_with_several_images(client, db):
    login(client)
    r = post_form(client, "/admin/products/new", FORM,
                  [make_image(), make_image("JPEG", (300, 200), "RGB", (0, 90, 200))])
    assert r.status_code == 302
    keys = keys_of(db, "IMG-1")
    assert len(keys) == 2
    # Ảnh nằm trong kho (thư mục catalog/images), đã thu nhỏ và nén thành JPEG
    stored = Image.open(os.path.join(CATALOG_IMAGES, keys[0]))
    assert stored.format == "JPEG" and max(stored.size) == 1000

    p = db.query(Product).filter_by(sku="IMG-1").one()
    body = client.get(f"/product/{p.id}").get_data(as_text=True)
    assert all(f"/media/{k}" in body for k in keys) and "gallery-thumbs" in body
    r = client.get(f"/media/{keys[0]}")
    assert r.status_code == 200 and r.mimetype == "image/jpeg" and "immutable" in r.headers["Cache-Control"]
    assert client.get("/media/../../etc/passwd").status_code == 404
    assert client.get("/media/zzz.jpg").status_code == 404


def test_cover_remove_and_append(client, db):
    login(client)
    imgs = [make_image("JPEG", (50, 50), "RGB", (i * 60, 0, 0)) for i in range(3)]
    post_form(client, "/admin/products/1", dict(FORM, sku="DT-001"), imgs)
    a, b, c = keys_of(db, "DT-001")

    # Chọn c làm ảnh chính, xóa a, thêm 1 ảnh mới
    data = dict(FORM, sku="DT-001", cover=c, remove_photo=[a])
    post_form(client, "/admin/products/1", data, [make_image("JPEG", (50, 50), "RGB", (0, 0, 255))])
    keys = keys_of(db, "DT-001")
    assert keys[:2] == [c, b] and len(keys) == 3

    # Lưu lại mà không đổi gì: giữ nguyên ảnh và thứ tự
    post_form(client, "/admin/products/1", dict(FORM, sku="DT-001", cover=c))
    assert keys_of(db, "DT-001") == keys


def test_photo_limit(client, db):
    login(client)
    imgs = [make_image("JPEG", (20, 20), "RGB", (i * 25, 0, 0)) for i in range(9)]
    r = post_form(client, "/admin/products/new", FORM, imgs)
    assert r.status_code == 400 and "tối đa 8 ảnh" in r.get_data(as_text=True)
    assert db.query(Product).filter_by(sku="IMG-1").count() == 0


def test_invalid_upload_rejected(client, db):
    login(client)
    r = post_form(client, "/admin/products/new", FORM, [io.BytesIO(b"<?php echo 1; ?>")])
    assert r.status_code == 400 and "không phải ảnh hợp lệ" in r.get_data(as_text=True)
    assert db.query(Product).filter_by(sku="IMG-1").count() == 0  # không tạo sản phẩm khi ảnh lỗi

    r = post_form(client, "/admin/products/new", FORM, [make_image("BMP", (10, 10), "RGB")])
    assert r.status_code == 400 and "Chỉ nhận ảnh" in r.get_data(as_text=True)


def test_upload_too_large(client):
    login(client)
    r = post_form(client, "/admin/products/new", FORM, [io.BytesIO(b"0" * (7 * 1024 * 1024))])
    assert r.status_code == 413


def test_upload_requires_admin(client, db):
    r = post_form(client, "/admin/products/1", dict(FORM, sku="DT-001"), [make_image()])
    assert "/login" in r.headers["Location"]
    assert keys_of(db, "DT-001") == []
