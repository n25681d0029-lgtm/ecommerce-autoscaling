from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from .models import User

bp = Blueprint("auth", __name__)


def _safe_next(nxt: str | None) -> str | None:
    """Chỉ cho chuyển hướng về đường dẫn nội bộ (chặn //evil.com, /\\evil.com, http://...)."""
    if nxt and nxt.startswith("/") and not nxt.startswith(("//", "/\\")):
        return nxt
    return None


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("full_name", "").strip()
        pw = request.form.get("password", "")
        if not email or not name or len(pw) < 6:
            flash("Nhập đủ thông tin, mật khẩu tối thiểu 6 ký tự.", "danger")
        elif len(email) > 120 or len(name) > 120 or "@" not in email:
            flash("Email hoặc họ tên không hợp lệ (tối đa 120 ký tự).", "danger")
        elif g.db.scalar(select(User).where(User.email == email)):
            flash("Email đã được đăng ký.", "danger")
        else:
            u = User(email=email, full_name=name, password_hash=generate_password_hash(pw))
            g.db.add(u)
            g.db.commit()
            _login(u)
            flash("Đăng ký thành công.", "success")
            return redirect(url_for("shop.index"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = g.db.scalar(select(User).where(User.email == email))
        if u and check_password_hash(u.password_hash, request.form.get("password", "")):
            _login(u)
            default = url_for("admin.dashboard") if u.is_admin else url_for("shop.index")
            return redirect(_safe_next(request.args.get("next")) or default)
        flash("Sai email hoặc mật khẩu.", "danger")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    cart = session.get("cart", {})
    session.clear()
    session["cart"] = cart
    return redirect(url_for("shop.index"))


@bp.route("/account", methods=["GET", "POST"])
def account():
    uid = session.get("user_id")
    if not uid:
        return redirect(url_for("auth.login", next=url_for("auth.account")))
    u = g.db.get(User, uid)
    if u is None:  # tài khoản đã bị xóa khỏi CSDL
        session.clear()
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        old, new = request.form.get("old_password", ""), request.form.get("new_password", "")
        if not check_password_hash(u.password_hash, old):
            flash("Mật khẩu hiện tại không đúng.", "danger")
        elif len(new) < 6:
            flash("Mật khẩu mới tối thiểu 6 ký tự.", "danger")
        elif new != request.form.get("confirm_password", ""):
            flash("Xác nhận mật khẩu mới không khớp.", "danger")
        else:
            u.password_hash = generate_password_hash(new)
            g.db.commit()
            flash("Đã đổi mật khẩu.", "success")
            return redirect(url_for("auth.account"))
    return render_template("account.html", user=u)


def _login(u: User) -> None:
    session["user_id"] = u.id
    session["user_name"] = u.full_name
    session["is_admin"] = u.is_admin
