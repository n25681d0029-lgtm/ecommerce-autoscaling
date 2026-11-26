"""Kịch bản kiểm thử tải cho CloudShop (Locust).

Hai loại người dùng ảo:
  - Shopper (mặc định): duyệt trang chủ, lọc danh mục, xem chi tiết, thêm giỏ,
    thỉnh thoảng đặt hàng. Mô phỏng khách mua sắm thực.
  - HeavyShopper: như Shopper nhưng có thêm request /api/heavy (mô phỏng tác vụ nặng CPU
    như tạo ảnh thumbnail / tính gợi ý) để đẩy CPU vượt ngưỡng Target Tracking nhanh hơn.

Chạy có giao diện:      locust -f loadtest/locustfile.py --host http://<ALB-DNS>
Chạy không giao diện:   locust -f loadtest/locustfile.py --host http://<ALB-DNS> --headless \
                         -u 150 -r 5 -t 15m --csv results/aws --html results/aws.html
Chọn loại người dùng:   thêm tên lớp ở cuối lệnh, ví dụ: ... HeavyShopper
"""
import random
import re

from locust import HttpUser, between, task

CATEGORIES = ["dien-thoai", "laptop", "may-tinh-bang", "am-thanh", "dong-ho", "phu-kien"]
KEYWORDS = ["laptop", "tai nghe", "sạc", "đồng hồ", "pin", "loa"]
TOKEN_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


class Shopper(HttpUser):
    wait_time = between(1, 3)
    product_ids: list[int] = []

    def on_start(self):
        r = self.client.get("/api/products", name="/api/products")
        if r.ok:
            Shopper.product_ids = [p["id"] for p in r.json()]
        self.csrf = ""
        self._refresh_token()

    def _refresh_token(self):
        """Website chống CSRF: mọi form POST phải kèm token của phiên (lấy từ HTML trang chủ)."""
        r = self.client.get("/", name="/")
        m = TOKEN_RE.search(r.text or "")
        self.csrf = m.group(1) if m else ""

    def _post(self, url, data, name):
        r = self.client.post(url, data=dict(data, csrf_token=self.csrf), name=name)
        if r.status_code == 400:  # phiên đổi (vd. cookie hết hạn): lấy token mới, thử lại một lần
            self._refresh_token()
            r = self.client.post(url, data=dict(data, csrf_token=self.csrf), name=name)
        return r

    def _pid(self) -> int:
        return random.choice(self.product_ids or [1])

    @task(5)
    def home(self):
        self.client.get("/", name="/")

    @task(3)
    def category(self):
        self.client.get(f"/?cat={random.choice(CATEGORIES)}&sort={random.choice(['new', 'price_asc', 'price_desc'])}",
                        name="/?cat=[slug]")

    @task(2)
    def search(self):
        self.client.get(f"/?q={random.choice(KEYWORDS)}", name="/?q=[keyword]")

    @task(6)
    def product(self):
        pid = self._pid()
        self.client.get(f"/product/{pid}", name="/product/[id]")
        self.client.get(f"/img/product/{pid}.svg", name="/img/product/[id].svg")  # ảnh minh họa (chưa có ảnh thật)

    @task(2)
    def add_to_cart(self):
        self._post(f"/cart/add/{self._pid()}", {"qty": 1}, "/cart/add/[id]")
        self.client.get("/cart", name="/cart")

    @task(1)
    def checkout(self):
        self._post(f"/cart/add/{self._pid()}", {"qty": 1}, "/cart/add/[id]")
        self._post("/checkout", {"name": "Khach Kiem Thu", "phone": "0900000000",
                                "address": "Dia chi kiem thu tai"}, "/checkout")

    @task(1)
    def whoami(self):
        self.client.get("/api/whoami", name="/api/whoami")


class HeavyShopper(Shopper):
    @task(4)
    def heavy(self):
        self.client.get("/api/heavy?ms=150", name="/api/heavy")
