from conftest import login


def register(client, email="binh@test.vn", pw="matkhau1"):
    return client.post("/register", data={"email": email, "full_name": "Bình", "password": pw})


def test_register_login_logout_keeps_cart(client):
    assert register(client).status_code == 302
    client.post("/cart/add/1")
    client.get("/logout")
    with client.session_transaction() as s:
        assert "user_id" not in s and s["cart"] == {"1": 1}
    r = login(client, "binh@test.vn", "matkhau1")
    assert r.headers["Location"] == "/"


def test_register_validation(client):
    assert "tối thiểu 6" in register(client, pw="123").get_data(as_text=True)
    register(client)
    assert "đã được đăng ký" in register(client).get_data(as_text=True)


def test_wrong_password(client):
    r = login(client, password="sai")
    assert r.status_code == 200 and "Sai email" in r.get_data(as_text=True)


def test_admin_login_goes_to_dashboard(client):
    assert login(client).headers["Location"] == "/admin/"


def test_login_next_allows_only_internal_paths(client):
    for bad in ["//evil.com", "/\\evil.com", "https://evil.com"]:
        r = client.post("/login?next=" + bad, data={"email": "admin@shop.local", "password": "Admin@123"})
        assert r.headers["Location"] == "/admin/", bad
        client.get("/logout")
    r = client.post("/login?next=/my-orders", data={"email": "admin@shop.local", "password": "Admin@123"})
    assert r.headers["Location"] == "/my-orders"


def test_account_requires_login(client):
    assert "/login" in client.get("/account").headers["Location"]


def test_change_password(client):
    register(client)
    r = client.post("/account", data={"old_password": "sai", "new_password": "moi123", "confirm_password": "moi123"})
    assert "không đúng" in r.get_data(as_text=True)
    r = client.post("/account", data={"old_password": "matkhau1", "new_password": "moi123",
                                      "confirm_password": "khac"})
    assert "không khớp" in r.get_data(as_text=True)
    client.post("/account", data={"old_password": "matkhau1", "new_password": "moi123", "confirm_password": "moi123"})
    client.get("/logout")
    assert login(client, "binh@test.vn", "matkhau1").status_code == 200  # mật khẩu cũ hết hiệu lực
    assert login(client, "binh@test.vn", "moi123").status_code == 302
