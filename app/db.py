"""Kết nối cơ sở dữ liệu dùng chung cho mọi máy chủ ứng dụng.

- Chạy cục bộ: mặc định SQLite (file shop.db trong thư mục instance/).
- Chạy trên AWS: biến môi trường DATABASE_URL trỏ tới Amazon RDS MySQL,
  ví dụ mysql+pymysql://admin:matkhau@<endpoint>:3306/shop
"""
import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, scoped_session, sessionmaker


class Base(DeclarativeBase):
    pass


def _default_sqlite_url() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inst = os.path.join(base_dir, "instance")
    os.makedirs(inst, exist_ok=True)
    return "sqlite:///" + os.path.join(inst, "shop.db")


DATABASE_URL = os.environ.get("DATABASE_URL") or _default_sqlite_url()

_engine_kwargs = {"pool_pre_ping": True, "future": True}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
else:
    # Mỗi worker giữ tối đa 5 + 5 kết nối, tự làm mới sau 30 phút
    _engine_kwargs.update(pool_size=5, max_overflow=5, pool_recycle=1800)

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = scoped_session(sessionmaker(bind=engine, expire_on_commit=False))


def wait_for_db(max_attempts: int = 60, delay: float = 5.0) -> None:
    """Chờ CSDL sẵn sàng (RDS có thể khởi động chậm hơn EC2)."""
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            if DATABASE_URL.startswith("sqlite"):
                with engine.connect() as conn:
                    conn.execute(text("PRAGMA journal_mode=WAL"))
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[db] Chưa kết nối được CSDL (lần {attempt}): {exc}", flush=True)
            time.sleep(delay)
    raise RuntimeError("Không kết nối được cơ sở dữ liệu")


def db_backend() -> str:
    return engine.dialect.name  # 'sqlite' hoặc 'mysql'
