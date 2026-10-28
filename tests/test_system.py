def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_whoami_not_cached(client):
    r = client.get("/api/whoami")
    d = r.get_json()
    assert d["instance_id"].startswith("local-") and "uptime" in d
    assert r.headers["Cache-Control"] == "no-store"


def test_api_products_only_active(client, db):
    from app.models import Product
    db.get(Product, 1).is_active = False
    db.commit()
    ids = [p["id"] for p in client.get("/api/products").get_json()]
    assert 1 not in ids and len(ids) == 35


def test_heavy_clamps_ms(client):
    assert client.get("/api/heavy?ms=99999").get_json()["ms"] == 500
    assert client.get("/api/heavy?ms=1").get_json()["ms"] == 10
    assert client.get("/api/heavy?ms=abc").get_json()["ms"] == 100


def test_system_pages(client):
    assert client.get("/system").status_code == 200
    assert "Cân bằng tải trực tiếp" in client.get("/system/live").get_data(as_text=True)


def test_custom_404_page(client):
    r = client.get("/khong-ton-tai")
    assert r.status_code == 404 and "Không tìm thấy trang" in r.get_data(as_text=True)
