"""Kho lưu trữ dùng chung cho ảnh sản phẩm và file catalog.json.

Cấu trúc giống nhau ở cả hai loại kho:
    catalog.json          danh sách sản phẩm (xem app/catalog.py)
    images/<mã băm>.jpg   ảnh sản phẩm, tên file = mã băm nội dung nên không bao giờ bị ghi đè

- LocalStore: thư mục `catalog/` trong repo. Đưa lên git được -> máy khác `git pull` là có cùng dữ liệu,
  EC2 `git clone` lúc khởi động cũng nhận được.
- S3Store: bucket S3 tạo cùng stack CloudFormation. Mọi EC2 và cả `run_local.py` (nếu có AWS credentials)
  cùng đọc/ghi một chỗ; ảnh được phát qua CloudFront.
"""
import json
import os
import tempfile

CATALOG_KEY = "catalog.json"
IMAGE_PREFIX = "images/"
IMAGE_CACHE = "public, max-age=31536000, immutable"


class StoreError(RuntimeError):
    pass


class Conflict(StoreError):
    """catalog.json vừa bị máy khác ghi đè trong lúc mình đang gộp: cần đọc lại và gộp lại."""


class LocalStore:
    kind = "local"

    def __init__(self, root: str):
        self.root = root

    @property
    def label(self) -> str:
        return f"thư mục {self.root}"

    def _path(self, key: str) -> str:
        return os.path.join(self.root, *key.split("/"))

    def read_catalog(self, etag: str | None = None) -> tuple[dict | None, str | None, bool]:
        """Trả về (catalog, etag, changed). changed=False nghĩa là giống lần đọc trước (etag không đổi)."""
        path = self._path(CATALOG_KEY)
        try:
            st = os.stat(path)
        except FileNotFoundError:
            return None, None, etag is not None
        tag = f"{st.st_mtime_ns}-{st.st_size}"
        if tag == etag:
            return None, tag, False
        with open(path, encoding="utf-8") as f:
            try:
                return json.load(f), tag, True
            except json.JSONDecodeError as exc:
                raise StoreError(f"{path} bị hỏng: {exc}") from None

    def write_catalog(self, data: dict, etag: str | None) -> str:
        # Ghi ra file tạm rồi đổi tên: máy/tiến trình khác không bao giờ đọc phải file ghi dở
        os.makedirs(self.root, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".catalog-", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(dump_catalog(data))
        os.replace(tmp, self._path(CATALOG_KEY))
        st = os.stat(self._path(CATALOG_KEY))
        return f"{st.st_mtime_ns}-{st.st_size}"

    def list_images(self) -> set[str]:
        try:
            return {n for n in os.listdir(self._path("images")) if not n.startswith(".")}
        except FileNotFoundError:
            return set()

    def has_image(self, key: str) -> bool:
        return os.path.isfile(self._path(IMAGE_PREFIX + key))

    def get_image(self, key: str) -> bytes:
        try:
            with open(self._path(IMAGE_PREFIX + key), "rb") as f:
                return f.read()
        except FileNotFoundError:
            raise KeyError(key) from None

    def put_image(self, key: str, data: bytes) -> None:
        path = self._path(IMAGE_PREFIX + key)
        if os.path.exists(path):
            return  # cùng mã băm = cùng nội dung
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".img-")
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)

    def delete_image(self, key: str) -> None:
        try:
            os.remove(self._path(IMAGE_PREFIX + key))
        except FileNotFoundError:
            pass

    def image_path(self, key: str) -> str:
        return self._path(IMAGE_PREFIX + key)

    def public_url(self, key: str) -> str | None:
        return None  # Flask tự phục vụ qua route /media/<key>


class S3Store:
    kind = "s3"

    def __init__(self, bucket: str, region: str | None = None, public_base_url: str = "", client=None):
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        if client is None:
            import boto3  # chỉ cần khi dùng S3
            from botocore.config import Config
            client = boto3.client("s3", region_name=region,
                                  config=Config(retries={"max_attempts": 3, "mode": "standard"},
                                                connect_timeout=5, read_timeout=15))
        self.s3 = client

    @property
    def label(self) -> str:
        return f"S3 bucket {self.bucket}"

    @staticmethod
    def _code(exc) -> str:
        return str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))

    def read_catalog(self, etag: str | None = None) -> tuple[dict | None, str | None, bool]:
        kw = {"IfNoneMatch": etag} if etag else {}
        try:
            r = self.s3.get_object(Bucket=self.bucket, Key=CATALOG_KEY, **kw)
        except Exception as exc:  # noqa: BLE001
            code = self._code(exc)
            if code in ("304", "NotModified"):
                return None, etag, False
            if code in ("NoSuchKey", "404"):
                return None, None, etag is not None
            raise StoreError(f"Không đọc được s3://{self.bucket}/{CATALOG_KEY}: {exc}") from exc
        try:
            return json.loads(r["Body"].read().decode("utf-8")), r["ETag"], True
        except ValueError as exc:
            raise StoreError(f"s3://{self.bucket}/{CATALOG_KEY} bị hỏng: {exc}") from None

    def write_catalog(self, data: dict, etag: str | None) -> str:
        kw = dict(Bucket=self.bucket, Key=CATALOG_KEY, Body=dump_catalog(data).encode("utf-8"),
                  ContentType="application/json; charset=utf-8", CacheControl="no-cache")
        # Ghi có điều kiện (S3 conditional writes): nếu máy khác vừa ghi, S3 trả 412 và mình gộp lại
        kw.update({"IfMatch": etag} if etag else {"IfNoneMatch": "*"})
        try:
            return self.s3.put_object(**kw)["ETag"]
        except Exception as exc:  # noqa: BLE001
            if self._code(exc) in ("PreconditionFailed", "412", "ConditionalRequestConflict", "409"):
                raise Conflict("catalog.json vừa được máy khác cập nhật") from exc
            raise StoreError(f"Không ghi được s3://{self.bucket}/{CATALOG_KEY}: {exc}") from exc

    def list_images(self) -> set[str]:
        keys, token = set(), None
        try:
            while True:
                kw = {"Bucket": self.bucket, "Prefix": IMAGE_PREFIX}
                if token:
                    kw["ContinuationToken"] = token
                r = self.s3.list_objects_v2(**kw)
                keys.update(o["Key"][len(IMAGE_PREFIX):] for o in r.get("Contents", []))
                if not r.get("IsTruncated"):
                    return keys
                token = r["NextContinuationToken"]
        except Exception as exc:  # noqa: BLE001
            raise StoreError(f"Không liệt kê được ảnh trên S3: {exc}") from exc

    def has_image(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=IMAGE_PREFIX + key)
            return True
        except Exception as exc:  # noqa: BLE001
            if self._code(exc) in ("404", "NoSuchKey", "NotFound"):
                return False
            raise StoreError(f"Không kiểm tra được ảnh trên S3: {exc}") from exc

    def get_image(self, key: str) -> bytes:
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=IMAGE_PREFIX + key)["Body"].read()
        except Exception as exc:  # noqa: BLE001
            if self._code(exc) in ("NoSuchKey", "404"):
                raise KeyError(key) from None
            raise StoreError(f"Không tải được ảnh từ S3: {exc}") from exc

    def put_image(self, key: str, data: bytes) -> None:
        try:
            self.s3.put_object(Bucket=self.bucket, Key=IMAGE_PREFIX + key, Body=data, ContentType="image/jpeg",
                               CacheControl=IMAGE_CACHE)
        except Exception as exc:  # noqa: BLE001
            raise StoreError(f"Không tải được ảnh lên S3: {exc}") from exc

    def delete_image(self, key: str) -> None:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=IMAGE_PREFIX + key)
        except Exception as exc:  # noqa: BLE001
            raise StoreError(f"Không xóa được ảnh trên S3: {exc}") from exc

    def public_url(self, key: str) -> str | None:
        return f"{self.public_base_url}/{IMAGE_PREFIX}{key}" if self.public_base_url else None


def dump_catalog(data: dict) -> str:
    # Thụt lề + giữ tiếng Việt + thứ tự cố định: diff trên git dễ đọc
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def default_catalog_dir() -> str:
    return os.environ.get("CATALOG_DIR") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "catalog")


_stores: dict = {}


def get_stores() -> tuple:
    """(primary, local). primary là nơi đọc/ghi chính; local là thư mục catalog/ trong repo.

    Có S3_BUCKET -> primary = S3, local = thư mục (bản sao để đưa lên git / dữ liệu ban đầu khi bucket còn trống).
    Không có -> primary = local = thư mục.
    """
    if "primary" not in _stores:
        local = LocalStore(default_catalog_dir())
        bucket = os.environ.get("S3_BUCKET", "").strip()
        if bucket:
            region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
            primary = S3Store(bucket, region, os.environ.get("MEDIA_BASE_URL", ""))
        else:
            primary = local
        _stores.update(primary=primary, local=local)
    return _stores["primary"], _stores["local"]


def set_stores(primary, local) -> None:
    """Dùng trong kiểm thử."""
    _stores.update(primary=primary, local=local)


def reset_stores() -> None:
    _stores.clear()
