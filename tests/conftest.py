"""Cấu hình chung cho pytest: mỗi test chạy trên một CSDL SQLite tạm, sạch, đã nạp dữ liệu mẫu.

Biến môi trường phải được đặt TRƯỚC khi import app vì app/db.py tạo engine ngay lúc import.
"""
import os
import re
import tempfile

_tmp = tempfile.mkdtemp(prefix="cloudshop-test-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db")
os.environ["DISABLE_IMDS"] = "1"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_PASSWORD"] = "Admin@123"
os.environ["CATALOG_DIR"] = os.path.join(_tmp, "catalog")  # kho catalog riêng cho kiểm thử, không đụng catalog/ thật
os.environ["SYNC_INTERVAL"] = "0"  # tắt đồng bộ nền; kiểm thử gọi sync() trực tiếp
os.environ.pop("S3_BUCKET", None)

import shutil  # noqa: E402

import pytest  # noqa: E402

from app import catalog, create_app  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.seed import init_db  # noqa: E402
from app.storage import reset_stores  # noqa: E402

_app = create_app()
_app.config["TESTING"] = True
_app.config["CSRF_ENABLED"] = False  # các test gửi form trực tiếp; CSRF có test riêng (test_ui.py)


def fresh_machine(clear_catalog: bool = False):
    """Giả lập một máy mới: CSDL trống, nạp dữ liệu mẫu rồi đồng bộ với kho catalog (giống lúc khởi động)."""
    SessionLocal.remove()
    Base.metadata.drop_all(engine)
    if clear_catalog:
        shutil.rmtree(os.environ["CATALOG_DIR"], ignore_errors=True)
    reset_stores()
    catalog.reset_state()
    init_db()
    catalog.sync(force=True)


@pytest.fixture()
def app():
    fresh_machine(clear_catalog=True)
    yield _app
    SessionLocal.remove()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    s = SessionLocal()
    yield s
    s.close()


def login(client, email="admin@shop.local", password="Admin@123"):
    return client.post("/login", data={"email": email, "password": password})


def place_order(client, pid=1, qty=2, phone="0900000000"):
    """Thêm sản phẩm vào giỏ rồi đặt hàng; trả về mã đơn (hoặc None nếu không tạo được)."""
    client.post(f"/cart/add/{pid}", data={"qty": qty})
    r = client.post("/checkout", data={"name": "Khách Test", "phone": phone, "address": "1 Đường Test"})
    m = re.search(r"/order/([A-Z0-9]+)$", r.headers.get("Location", ""))
    return m.group(1) if m else None
