"""Chạy website trên máy cá nhân (Windows/macOS/Linux) bằng waitress.

    python run_local.py            -> http://127.0.0.1:8000
    python run_local.py --port 5000 --threads 8

Gunicorn không chạy được trên Windows nên bản cục bộ dùng waitress;
trên EC2 (Linux) hệ thống dùng gunicorn.
"""
import argparse
import os
import sys

from dotenv_lite import load_env

# Khi output bị chuyển hướng (file log, tiến trình con) Windows dùng code page cục bộ (vd. cp932/cp1252)
# và print tiếng Việt sẽ báo UnicodeEncodeError; ép UTF-8 để luôn chạy được.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

load_env()

from waitress import serve  # noqa: E402

from app import create_app  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()
    app = create_app()
    print(f"CloudShop đang chạy tại http://{a.host}:{a.port}  (Ctrl+C để dừng)")
    print("Tài khoản quản trị mặc định: admin@shop.local / Admin@123")
    serve(app, host=a.host, port=a.port, threads=a.threads)
