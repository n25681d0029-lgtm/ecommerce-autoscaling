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

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.seed import init_db  # noqa: E402

_app = create_app()
_app.config["TESTING"] = True


@pytest.fixture()
def app():
    SessionLocal.remove()
    Base.metadata.drop_all(engine)
    init_db()
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
