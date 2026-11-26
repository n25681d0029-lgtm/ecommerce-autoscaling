"""Ghi/xóa các biến kết nối kho ảnh (S3 + CloudFront) trong file .env để run_local.py dùng chung với AWS."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, ".env")
MARK = "# --- Kho ảnh/catalog dùng chung với AWS (do scripts/deploy.py ghi, destroy.py xóa) ---"
KEYS = ("S3_BUCKET", "MEDIA_BASE_URL", "AWS_REGION")


def _strip(lines: list[str]) -> list[str]:
    return [ln for ln in lines if ln.strip() != MARK and ln.split("=", 1)[0].strip() not in KEYS]


def write_media_env(values: dict, path: str = ENV_PATH) -> None:
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    lines = _strip(lines)
    while lines and not lines[-1].strip():
        lines.pop()
    lines += ["", MARK] + [f"{k}={values[k]}" for k in KEYS if values.get(k)]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def clear_media_env(path: str = ENV_PATH) -> bool:
    if not os.path.exists(path):
        return False
    lines = open(path, encoding="utf-8").read().splitlines()
    kept = _strip(lines)
    if kept == lines:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(kept).rstrip("\n") + "\n")
    return True
