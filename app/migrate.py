"""Nâng cấp cấu trúc CSDL cũ (instance/shop.db hoặc RDS đã có dữ liệu) cho phiên bản có đồng bộ catalog.

create_all() chỉ tạo bảng còn thiếu, không thêm cột vào bảng đã có, nên các cột mới của `products`
được thêm bằng ALTER TABLE ở đây. An toàn khi nhiều instance chạy cùng lúc: lệnh nào đã được
instance khác làm rồi sẽ báo lỗi và được bỏ qua.
"""
import hashlib

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from .models import Product, ProductPhoto


def _quiet(engine, sql: str) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    except (OperationalError, ProgrammingError) as exc:
        print(f"[migrate] Bỏ qua ({exc.__class__.__name__}): {sql}", flush=True)


def image_key(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:32] + ".jpg"


def migrate(engine) -> None:
    from .catalog import SEED_TIME, now  # tránh import vòng
    from .seed import PRODUCTS

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    if "products" not in tables:
        return
    cols = {c["name"] for c in insp.get_columns("products")}
    dt = "DATETIME(6)" if engine.dialect.name == "mysql" else "DATETIME"
    for name, ddl in (("uid", "VARCHAR(64)"), ("updated_at", dt), ("deleted_at", dt)):
        if name not in cols:
            _quiet(engine, f"ALTER TABLE products ADD COLUMN {name} {ddl} NULL")

    # Điền uid cho sản phẩm cũ. uid suy ra từ SKU nên cùng một sản phẩm mẫu ở hai máy khác nhau
    # có cùng uid và được gộp làm một khi đồng bộ.
    seed = {sku: (name, cat, price, desc, hue) for sku, name, cat, price, _stock, desc, hue in PRODUCTS}
    with Session(engine) as s:
        rows = s.scalars(select(Product).where(Product.uid.is_(None))).all()
        for p in rows:
            p.uid = "sku:" + p.sku
            same_as_seed = seed.get(p.sku) == (p.name, p.category.slug, p.price, p.description, p.hue)
            # Sản phẩm mẫu chưa ai sửa giữ mốc SEED_TIME; sản phẩm đã sửa/tự thêm coi như vừa sửa xong,
            # nhờ vậy chỉnh sửa cũ trên máy này được đẩy lên kho chung ở lần đồng bộ đầu tiên.
            p.updated_at = SEED_TIME if same_as_seed and p.is_active else now()
        if rows:
            try:
                s.commit()
                print(f"[migrate] Đã gán uid cho {len(rows)} sản phẩm", flush=True)
            except IntegrityError:
                s.rollback()

    indexed = any(ix.get("column_names") == ["uid"] for ix in insp.get_indexes("products")) or any(
        uc.get("column_names") == ["uid"] for uc in insp.get_unique_constraints("products"))
    if not indexed:
        _quiet(engine, "CREATE UNIQUE INDEX uq_products_uid ON products (uid)")

    if "product_images" in tables:
        _migrate_blob_images(engine)


def _migrate_blob_images(engine) -> None:
    """Bản trước lưu 1 ảnh/sản phẩm dạng BLOB trong bảng product_images: chuyển sang kho ảnh rồi xóa bảng."""
    from .catalog import now
    from .storage import get_stores

    primary, local = get_stores()
    with Session(engine) as s:
        rows = s.execute(text("SELECT product_id, data FROM product_images")).all()
        for pid, data in rows:
            p = s.get(Product, pid)
            if p is None or not data:
                continue
            key = image_key(bytes(data))
            primary.put_image(key, bytes(data))
            if primary is not local:
                local.put_image(key, bytes(data))
            if key not in [ph.key for ph in p.photos]:
                p.photos.insert(0, ProductPhoto(key=key))
                for i, ph in enumerate(p.photos):
                    ph.position = i
                p.updated_at = now()
        s.commit()
        if rows:
            print(f"[migrate] Đã chuyển {len(rows)} ảnh từ bảng product_images sang {primary.label}", flush=True)
    _quiet(engine, "DROP TABLE product_images")
