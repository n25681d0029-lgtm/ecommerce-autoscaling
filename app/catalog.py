"""Đồng bộ danh mục sản phẩm giữa các máy (máy cá nhân chạy run_local.py, các EC2 trên AWS, máy của bạn khác).

Vấn đề: mỗi nơi có CSDL riêng (SQLite trên máy cá nhân, RDS trên AWS) nên sửa sản phẩm ở nơi này
nơi khác không thấy. Giải pháp: mọi nơi cùng gộp với một file `catalog.json` ở kho dùng chung
(S3 khi có AWS, thư mục `catalog/` trong repo khi không có), kèm ảnh sản phẩm ở cùng kho.

Quy tắc gộp: mỗi sản phẩm có `uid` cố định và `updated_at` (lần quản trị viên sửa cuối). Với mỗi uid,
bản có `updated_at` mới nhất thắng ("last writer wins"), áp dụng cho cả CSDL lẫn catalog.json.
Sản phẩm bị xóa để lại "bia mộ" {uid, deleted, updated_at} để máy khác cũng xóa theo
thay vì tạo lại nó từ bản cũ.

Đồng bộ chạy: lúc khởi động, ngay sau mỗi lần quản trị viên lưu/xóa, khi bấm "Đồng bộ ngay",
và định kỳ mỗi SYNC_INTERVAL giây (mặc định 30) ở nền.

Những thứ KHÔNG đồng bộ: đơn hàng, tài khoản, và số tồn kho bị trừ khi khách đặt hàng
(tồn kho chỉ được đồng bộ khi quản trị viên sửa sản phẩm hoặc bấm "Bổ sung kho").
"""
import os
import random
import threading
import time
import traceback
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .db import SessionLocal
from .models import Category, Product, ProductPhoto
from .storage import Conflict, StoreError, get_stores

FORMAT = 1
SEED_TIME = datetime(2000, 1, 1)  # updated_at của dữ liệu mẫu: mọi chỉnh sửa thật đều mới hơn
LOCAL_GC_AGE = 3600  # chỉ dọn ảnh mồ côi trong thư mục catalog/ đã cũ hơn 1 giờ

_lock = threading.Lock()
state = {"hub_etag": None, "hub_doc": None, "seed_etag": None, "seed_doc": None, "local_mark": None,
         "last_sync": None, "last_error": None, "last_doc": None, "primary_images": None}


def reset_state() -> None:
    for k in state:
        state[k] = None


def now() -> datetime:
    return datetime.utcnow()


def iso(dt: datetime | None) -> str:
    return (dt or SEED_TIME).strftime("%Y-%m-%dT%H:%M:%S.%f")


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s)


def mirror_enabled() -> bool:
    # Trên EC2 tắt (CATALOG_MIRROR=0): thư mục mã nguồn chỉ để đọc dữ liệu ban đầu
    return os.environ.get("CATALOG_MIRROR", "1") != "0"


# --------------------------------------------------------------------- chuyển đổi
def entry_of(p: Product) -> dict:
    if p.deleted_at is not None:
        return {"uid": p.uid, "deleted": True, "updated_at": iso(p.updated_at)}
    return {"uid": p.uid, "sku": p.sku, "name": p.name, "category": p.category.slug, "price": p.price,
            "stock": p.stock, "description": p.description or "", "hue": p.hue, "is_active": bool(p.is_active),
            "images": [ph.key for ph in p.photos], "updated_at": iso(p.updated_at)}


def parse_doc(doc: dict | None) -> tuple[dict, dict]:
    if not doc:
        return {}, {}
    cats = {c["slug"]: c["name"] for c in doc.get("categories", []) if c.get("slug")}
    entries = {e["uid"]: e for e in doc.get("products", []) if e.get("uid") and e.get("updated_at")}
    return cats, entries


def build_doc(cats: dict, entries: dict) -> dict:
    return {"format": FORMAT,
            "categories": [{"slug": s, "name": n} for s, n in sorted(cats.items())],
            "products": [entries[u] for u in sorted(entries)]}


def merge(*sources: dict) -> dict:
    """Gộp nhiều nguồn {uid: entry}: bản mới nhất thắng; bằng nhau thì nguồn đứng trước thắng."""
    out: dict = {}
    for src in sources:
        for uid, e in src.items():
            cur = out.get(uid)
            if cur is None or parse_time(e["updated_at"]) > parse_time(cur["updated_at"]):
                out[uid] = e
    return out


def tombstone_sku(p: Product) -> str:
    """Đổi SKU của sản phẩm đã xóa để SKU cũ dùng lại được cho sản phẩm mới."""
    suffix = f"~del{p.id}"
    return p.sku if p.sku.endswith(suffix) else p.sku[:40 - len(suffix)] + suffix


def mark_deleted(p: Product, when: datetime | None = None) -> None:
    when = when or now()
    p.deleted_at = when
    p.updated_at = when
    p.is_active = False
    p.sku = tombstone_sku(p)
    p.photos = []


# --------------------------------------------------------------------- áp dụng vào CSDL
def apply_entries(db, cats: dict, entries: dict) -> int:
    """Đưa các bản mới hơn vào CSDL của máy này. Trả về số sản phẩm đã thay đổi."""
    by_slug = {c.slug: c for c in db.scalars(select(Category)).all()}
    for slug, name in cats.items():
        if slug not in by_slug:
            c = Category(slug=slug, name=name)
            db.add(c)
            by_slug[slug] = c
    db.commit()

    local = {p.uid: p for p in db.scalars(select(Product).where(Product.uid.is_not(None))).all()}
    changed = 0
    # Bia mộ trước: SKU của sản phẩm bị xóa được giải phóng trước khi sản phẩm khác dùng lại nó
    for uid, e in sorted(entries.items(), key=lambda kv: (not kv[1].get("deleted"), kv[0])):
        p = local.get(uid)
        t = parse_time(e["updated_at"])
        if p is not None and (p.updated_at or SEED_TIME) >= t:
            continue
        try:
            if e.get("deleted"):
                if p is None:
                    continue  # chưa từng có ở máy này: không cần làm gì
                mark_deleted(p, t)
            else:
                cat = by_slug.get(e.get("category"))
                if cat is None:
                    print(f"[catalog] Bỏ qua {e.get('sku')}: danh mục {e.get('category')} không tồn tại", flush=True)
                    continue
                clash = db.scalar(select(Product).where(Product.sku == e["sku"], Product.uid != uid))
                if clash is not None:
                    print(f"[catalog] Bỏ qua {e['sku']}: SKU đang dùng cho sản phẩm khác ở máy này "
                          f"(uid {clash.uid}). Hãy đổi SKU một trong hai sản phẩm.", flush=True)
                    continue
                if p is None:
                    p = Product(uid=uid)
                    db.add(p)
                p.sku, p.name, p.category_id = e["sku"], e["name"], cat.id
                p.price, p.stock, p.hue = int(e["price"]), int(e["stock"]), int(e.get("hue", 210))
                p.description, p.is_active = e.get("description", ""), bool(e.get("is_active", True))
                p.deleted_at, p.updated_at = None, t
                keys = list(e.get("images", []))
                if [ph.key for ph in p.photos] != keys:
                    p.photos = [ProductPhoto(key=k, position=i) for i, k in enumerate(keys)]
            db.commit()
            local[uid] = p
            changed += 1
        except IntegrityError:
            # Thường do tiến trình khác vừa áp dụng cùng bản ghi; lần đồng bộ sau sẽ thấy đã khớp
            db.rollback()
    return changed


def local_entries(db) -> dict:
    return {p.uid: entry_of(p) for p in db.scalars(select(Product).where(Product.uid.is_not(None))).all()}


def local_mark(db) -> tuple:
    """Dấu hiệu CSDL của máy này có chỉnh sửa mới (để bỏ qua lần đồng bộ định kỳ khi không có gì thay đổi)."""
    return tuple(db.execute(select(func.max(Product.updated_at), func.count(Product.id))).one())


# --------------------------------------------------------------------- ảnh
def _reconcile_images(primary, local, keys: set[str]) -> None:
    if primary is local:
        return
    have = state["primary_images"]
    if have is None:
        have = primary.list_images()
    missing = keys - have
    for k in sorted(missing):
        if primary.has_image(k):  # máy khác vừa tải lên sau lần liệt kê trước
            have.add(k)
        elif local.has_image(k):  # ảnh có trong thư mục catalog/ (vd. lấy từ git) nhưng chưa có trên S3
            primary.put_image(k, local.get_image(k))
            have.add(k)
        else:
            print(f"[catalog] Thiếu file ảnh {k} ở cả hai kho", flush=True)
    state["primary_images"] = have
    if mirror_enabled():
        local_have = local.list_images()
        for k in sorted((keys & have) - local_have):
            try:
                local.put_image(k, primary.get_image(k))
            except KeyError:
                pass


def _gc_local(local, keys: set[str]) -> None:
    """Xóa ảnh không còn sản phẩm nào dùng khỏi thư mục catalog/ để repo git không phình to."""
    limit = time.time() - LOCAL_GC_AGE
    for k in local.list_images() - keys:
        try:
            if os.path.getmtime(local.image_path(k)) < limit:
                local.delete_image(k)
        except OSError:
            pass


def image_keys(entries: dict) -> set[str]:
    return {k for e in entries.values() if not e.get("deleted") for k in e.get("images", [])}


# --------------------------------------------------------------------- đồng bộ
def sync(db=None, force: bool = False) -> dict:
    """Gộp CSDL của máy này với kho dùng chung. An toàn khi nhiều tiến trình/máy cùng chạy."""
    with _lock:
        own = db is None
        db = db or SessionLocal()
        try:
            result = _sync(db, force)
            state["last_error"] = None
            state["last_sync"] = now()
            return result
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            state["last_error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if own:
                SessionLocal.remove()


def _sync(db, force: bool) -> dict:
    primary, local = get_stores()
    separate = primary is not local
    for _attempt in range(5):
        hub_doc, hub_etag, hub_changed = primary.read_catalog(None if force else state["hub_etag"])
        if not hub_changed:
            hub_doc = state["hub_doc"]
        seed_changed = False
        seed_doc = None
        if separate:
            seed_doc, seed_etag, seed_changed = local.read_catalog(None if force else state["seed_etag"])
            if not seed_changed:
                seed_doc = state["seed_doc"]
            state["seed_etag"], state["seed_doc"] = seed_etag, seed_doc
        mark = local_mark(db)
        if not (force or hub_changed or seed_changed or mark != state["local_mark"]):
            return {"status": "unchanged", "applied": 0, "pushed": False}

        hub_cats, hub_entries = parse_doc(hub_doc)
        seed_cats, seed_entries = parse_doc(seed_doc)
        db_entries = local_entries(db)
        cats = {c.slug: c.name for c in db.scalars(select(Category)).all()}
        cats.update(seed_cats)
        cats.update(hub_cats)
        merged = merge(hub_entries, seed_entries, db_entries)
        applied = apply_entries(db, cats, merged)

        new_doc = build_doc(cats, merged)
        keys = image_keys(merged)
        if force or new_doc != state["last_doc"]:
            _reconcile_images(primary, local, keys)
        pushed = False
        if new_doc != hub_doc:
            try:
                hub_etag = primary.write_catalog(new_doc, hub_etag if hub_doc is not None else None)
                pushed = True
            except Conflict:
                state["hub_etag"] = state["hub_doc"] = None
                time.sleep(random.uniform(0.05, 0.3))
                continue  # máy khác vừa ghi: đọc lại và gộp lại
        if separate and mirror_enabled() and new_doc != seed_doc:
            state["seed_etag"] = local.write_catalog(new_doc, None)
            state["seed_doc"] = new_doc
        if mirror_enabled() or not separate:
            _gc_local(local, keys)
        state.update(hub_etag=hub_etag, hub_doc=new_doc, last_doc=new_doc, local_mark=local_mark(db))
        if applied or pushed:
            print(f"[catalog] Đồng bộ với {primary.label}: nhận {applied} thay đổi"
                  f"{', đã ghi catalog.json' if pushed else ''}", flush=True)
        return {"status": "ok", "applied": applied, "pushed": pushed}
    raise StoreError("catalog.json bị nhiều máy ghi cùng lúc, thử lại sau")


def try_sync(db=None, force: bool = False) -> str | None:
    """Đồng bộ, trả về thông báo lỗi (hoặc None) thay vì ném ngoại lệ."""
    try:
        sync(db, force)
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"[catalog] Đồng bộ lỗi: {exc}", flush=True)
        return str(exc)


def status() -> dict:
    primary, local = get_stores()
    return {"store": primary.label, "kind": primary.kind, "mirror": local.label if primary is not local else None,
            "last_sync": state["last_sync"], "last_error": state["last_error"]}


_bg = {"thread": None}


def start_background(interval: float) -> None:
    """Đồng bộ định kỳ để thay đổi ở máy khác hiện ra mà không cần khởi động lại."""
    if interval <= 0 or _bg["thread"] is not None:
        return

    def loop():
        while True:
            time.sleep(interval * random.uniform(0.8, 1.2))  # lệch nhau để các worker không gọi S3 cùng lúc
            try:
                sync()
            except Exception:  # noqa: BLE001
                print("[catalog] Đồng bộ nền lỗi:\n" + traceback.format_exc(limit=2), flush=True)

    t = threading.Thread(target=loop, name="catalog-sync", daemon=True)
    t.start()
    _bg["thread"] = t
