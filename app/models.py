from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import DATETIME as MYSQL_DATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# DATETIME của MySQL mặc định chỉ lưu đến giây; dùng DATETIME(6) để so sánh "bản nào mới hơn" chính xác
TIMESTAMP6 = DateTime().with_variant(MYSQL_DATETIME(fsp=6), "mysql")
MAX_PHOTOS = 8  # số ảnh tối đa mỗi sản phẩm


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    price: Mapped[int] = mapped_column(Integer)  # đơn vị: đồng
    stock: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    hue: Mapped[int] = mapped_column(Integer, default=210)  # màu ảnh minh họa
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # --- Đồng bộ catalog giữa các máy (xem app/catalog.py) ---
    # uid: mã định danh bền vững, giống nhau trên mọi máy (id tự tăng thì mỗi CSDL một khác)
    uid: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    # Thời điểm quản trị viên sửa lần cuối; bản có updated_at mới hơn sẽ thắng khi đồng bộ.
    # Đặt hàng (trừ kho) KHÔNG đổi giá trị này.
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP6, nullable=True)
    # Xóa mềm: giữ dòng để lịch sử đơn hàng còn nguyên và để máy khác biết sản phẩm đã bị xóa
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP6, nullable=True)
    category: Mapped[Category] = relationship(back_populates="products")
    # selectin: nạp ảnh của cả trang sản phẩm bằng 1 truy vấn
    photos: Mapped[list["ProductPhoto"]] = relationship(back_populates="product", lazy="selectin",
                                                        order_by="ProductPhoto.position",
                                                        cascade="all, delete-orphan")

    @property
    def cover_key(self) -> str | None:
        return self.photos[0].key if self.photos else None


class ProductPhoto(Base):
    """Một ảnh của sản phẩm (ảnh đầu tiên theo position là ảnh chính).

    File ảnh nằm ở kho lưu trữ dùng chung (S3 trên AWS, thư mục catalog/images khi chạy cục bộ),
    CSDL chỉ giữ tên file. Tên file là mã băm nội dung nên ảnh không bao giờ bị ghi đè:
    trình duyệt/CloudFront lưu đệm vĩnh viễn được và đồng bộ chỉ cần chép các file còn thiếu.
    """
    __tablename__ = "product_photos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    key: Mapped[str] = mapped_column(String(80))
    product: Mapped[Product] = relationship(back_populates="photos")


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    address: Mapped[str] = mapped_column(String(255))
    total: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="Mới")
    served_by: Mapped[str] = mapped_column(String(60), default="")  # instance tạo đơn
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(160))
    price: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    order: Mapped[Order] = relationship(back_populates="items")


ORDER_STATUSES = ["Mới", "Đã xác nhận", "Đang giao", "Hoàn thành", "Đã hủy"]
