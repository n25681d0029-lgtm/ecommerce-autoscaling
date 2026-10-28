"""Dữ liệu mẫu cho cửa hàng demo (tên sản phẩm là hư cấu, giá tham khảo theo VNĐ)."""
import os
import random
import time

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from werkzeug.security import generate_password_hash

from .db import Base, SessionLocal, engine
from .models import Category, Product, User

CATEGORIES = [
    ("Điện thoại", "dien-thoai"),
    ("Laptop", "laptop"),
    ("Máy tính bảng", "may-tinh-bang"),
    ("Âm thanh", "am-thanh"),
    ("Đồng hồ thông minh", "dong-ho"),
    ("Phụ kiện", "phu-kien"),
]

# (sku, tên, slug danh mục, giá, tồn kho, mô tả, hue)
PRODUCTS = [
    ("DT-001", "Điện thoại Nova A15 128GB", "dien-thoai", 4_990_000, 50, "Màn hình 6,5 inch, pin 5000 mAh, camera kép 50 MP.", 200),
    ("DT-002", "Điện thoại Nova A35 256GB", "dien-thoai", 7_490_000, 40, "Màn hình AMOLED 120 Hz, sạc nhanh 45 W.", 215),
    ("DT-003", "Điện thoại Orbit X Pro 512GB", "dien-thoai", 24_990_000, 15, "Chip hiệu năng cao, camera tele 5x, khung titan.", 260),
    ("DT-004", "Điện thoại Orbit X 256GB", "dien-thoai", 18_490_000, 25, "Màn hình 6,1 inch, chống nước IP68.", 250),
    ("DT-005", "Điện thoại Lumo C3 64GB", "dien-thoai", 2_690_000, 80, "Máy phổ thông, pin bền, 2 SIM.", 140),
    ("DT-006", "Điện thoại gập Flexa Z 256GB", "dien-thoai", 32_990_000, 8, "Màn hình gập 7,6 inch, bút cảm ứng.", 300),
    ("LT-001", "Laptop Aero 14 Core i5 16GB/512GB", "laptop", 16_990_000, 20, "Mỏng nhẹ 1,3 kg, màn hình 14 inch 2.8K.", 190),
    ("LT-002", "Laptop Aero 16 Core i7 16GB/1TB", "laptop", 23_490_000, 12, "Màn hình 16 inch 120 Hz, bàn phím số.", 185),
    ("LT-003", "Laptop gaming Raptor G15 RTX 4060", "laptop", 27_990_000, 10, "Tản nhiệt kép, màn hình 165 Hz.", 0),
    ("LT-004", "Laptop văn phòng Basic 15 Ryzen 5", "laptop", 11_490_000, 30, "Ổ SSD 512GB, Wi-Fi 6.", 120),
    ("LT-005", "Laptop sinh viên Study 14 Core i3", "laptop", 9_290_000, 35, "Pin 10 giờ, nặng 1,4 kg.", 160),
    ("LT-006", "Laptop đồ họa Studio 16 RTX 4070", "laptop", 45_990_000, 5, "Màn hình OLED 4K, chuẩn màu 100% DCI-P3.", 280),
    ("TB-001", "Máy tính bảng Tab S 11 inch 128GB", "may-tinh-bang", 8_990_000, 25, "Hỗ trợ bút, 4 loa.", 230),
    ("TB-002", "Máy tính bảng Tab Lite 8 inch 64GB", "may-tinh-bang", 3_490_000, 40, "Nhỏ gọn, phù hợp đọc sách.", 170),
    ("TB-003", "Máy tính bảng Tab Pro 13 inch 256GB", "may-tinh-bang", 21_990_000, 10, "Màn hình 144 Hz, bàn phím rời.", 275),
    ("TB-004", "Máy đọc sách E-Ink Paper 7", "may-tinh-bang", 3_990_000, 30, "Màn hình E-Ink 300 ppi, chống nước.", 40),
    ("AT-001", "Tai nghe không dây ANC Pods 2", "am-thanh", 1_990_000, 100, "Chống ồn chủ động, pin 30 giờ kèm hộp.", 330),
    ("AT-002", "Tai nghe chụp tai Studio Max", "am-thanh", 5_490_000, 20, "Driver 40 mm, chống ồn, kết nối đa điểm.", 10),
    ("AT-003", "Loa Bluetooth Boom Mini", "am-thanh", 890_000, 120, "Chống nước IPX7, pin 12 giờ.", 25),
    ("AT-004", "Loa thanh Soundbar 2.1 300W", "am-thanh", 4_290_000, 15, "Kèm loa siêu trầm không dây.", 345),
    ("AT-005", "Tai nghe thể thao Run Fit", "am-thanh", 690_000, 90, "Móc tai, chống mồ hôi.", 95),
    ("AT-006", "Micro thu âm USB Podcast", "am-thanh", 1_590_000, 25, "Thu âm cardioid, đèn báo tắt tiếng.", 60),
    ("DH-001", "Đồng hồ thông minh Fit Band 8", "dong-ho", 990_000, 150, "Đo nhịp tim, SpO2, pin 14 ngày.", 150),
    ("DH-002", "Đồng hồ thông minh Watch S 45mm", "dong-ho", 6_990_000, 30, "GPS, eSIM, màn hình luôn bật.", 205),
    ("DH-003", "Đồng hồ trẻ em Kid Safe 4G", "dong-ho", 1_490_000, 45, "Định vị, gọi video.", 50),
    ("DH-004", "Đồng hồ thể thao Trail GPS", "dong-ho", 8_490_000, 12, "Bản đồ ngoại tuyến, pin 20 ngày.", 110),
    ("PK-001", "Sạc nhanh GaN 65W 3 cổng", "phu-kien", 590_000, 200, "2 USB-C + 1 USB-A, gập chân cắm.", 75),
    ("PK-002", "Pin dự phòng 20000 mAh 22,5W", "phu-kien", 490_000, 180, "Sạc 2 thiết bị cùng lúc.", 85),
    ("PK-003", "Cáp USB-C to USB-C 100W 2m", "phu-kien", 190_000, 300, "Bọc dù, truyền dữ liệu 480 Mbps.", 180),
    ("PK-004", "Chuột không dây Silent M2", "phu-kien", 290_000, 150, "Click êm, 3 mức DPI.", 220),
    ("PK-005", "Bàn phím cơ không dây K75", "phu-kien", 1_290_000, 60, "Switch hot-swap, kết nối 3 chế độ.", 265),
    ("PK-006", "Ổ cứng SSD di động 1TB", "phu-kien", 1_890_000, 50, "Tốc độ 1050 MB/s, USB 3.2 Gen 2.", 240),
    ("PK-007", "Hub USB-C 7 trong 1", "phu-kien", 650_000, 90, "HDMI 4K, đọc thẻ SD, sạc PD 100W.", 195),
    ("PK-008", "Ốp lưng chống sốc trong suốt", "phu-kien", 150_000, 400, "Viền TPU, chống ố vàng.", 130),
    ("PK-009", "Webcam Full HD 1080p", "phu-kien", 790_000, 70, "Micro kép giảm ồn, kẹp màn hình.", 15),
    ("PK-010", "Giá đỡ laptop nhôm", "phu-kien", 350_000, 110, "Điều chỉnh 6 nấc độ cao.", 35),
]


def init_db() -> None:
    """Tạo bảng và nạp dữ liệu mẫu nếu CSDL còn trống.

    An toàn khi nhiều instance khởi động cùng lúc: các khóa unique (slug, sku, email)
    khiến instance đến sau gặp IntegrityError và chỉ việc bỏ qua.
    """
    # Nhiều worker gunicorn cùng gọi create_all có thể đụng độ "table already exists"
    for attempt in range(5):
        try:
            Base.metadata.create_all(engine)
            break
        except (OperationalError, ProgrammingError) as exc:
            print(f"[seed] create_all lần {attempt + 1} lỗi, thử lại: {exc.__class__.__name__}", flush=True)
            time.sleep(random.uniform(0.5, 2.0))
    s = SessionLocal()
    try:
        if s.scalar(select(func.count(Product.id))) == 0:
            cats = {}
            for name, slug in CATEGORIES:
                c = Category(name=name, slug=slug)
                s.add(c)
                cats[slug] = c
            s.flush()
            for sku, name, cslug, price, stock, desc, hue in PRODUCTS:
                s.add(Product(sku=sku, name=name, category_id=cats[cslug].id, price=price,
                              stock=stock, description=desc, hue=hue))
            s.commit()
            print(f"[seed] Đã nạp {len(CATEGORIES)} danh mục, {len(PRODUCTS)} sản phẩm", flush=True)
    except IntegrityError:
        s.rollback()
        print("[seed] Instance khác đã nạp dữ liệu mẫu, bỏ qua", flush=True)
    finally:
        s.close()

    s = SessionLocal()
    try:
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@shop.local")
        if not s.scalar(select(User).where(User.email == admin_email)):
            s.add(User(email=admin_email, full_name="Quản trị viên",
                       password_hash=generate_password_hash(os.environ.get("ADMIN_PASSWORD", "Admin@123")),
                       is_admin=True))
            s.commit()
    except IntegrityError:
        s.rollback()
    finally:
        s.close()
        SessionLocal.remove()
