"""Chống CSRF (giả mạo request từ trang web khác) cho mọi form POST.

Mỗi phiên có một token ngẫu nhiên lưu trong cookie phiên (đã ký bằng SECRET_KEY chung, nên mọi instance
sau Load Balancer đều kiểm tra được). Form nào cũng phải gửi kèm token đó; trang lạ không đọc được token
nên không thể tự gửi form "đặt hàng", "xóa sản phẩm"... thay người dùng.

Template dùng: <form method="post">{{ csrf_field() }} ...</form>
Gọi bằng JavaScript/công cụ: gửi header X-CSRF-Token hoặc trường csrf_token.
"""
import hmac
import secrets

from flask import abort, current_app, request, session
from markupsafe import Markup

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def csrf_token() -> str:
    tok = session.get("_csrf")
    if not tok:
        tok = session["_csrf"] = secrets.token_urlsafe(24)
    return tok


def csrf_field() -> Markup:
    return Markup(f'<input type="hidden" name="csrf_token" value="{csrf_token()}">')


def check_csrf() -> None:
    if request.method in SAFE_METHODS or not current_app.config.get("CSRF_ENABLED", True):
        return
    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
    expected = session.get("_csrf", "")
    if not expected or not hmac.compare_digest(sent, expected):
        abort(400, description="csrf")


def init_app(app) -> None:
    app.before_request(check_csrf)
    app.jinja_env.globals.update(csrf_token=csrf_token, csrf_field=csrf_field)

    @app.after_request
    def _headers(resp):
        # Chặn trang khác nhúng website vào iframe (clickjacking) và đoán sai kiểu nội dung
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp
