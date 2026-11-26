"""Nghiệp vụ đơn hàng dùng chung cho khách hàng và trang quản trị."""
from sqlalchemy import select

from .models import Order, Product

CANCELLED = "Đã hủy"
NEW = "Mới"


def cancel_order(db, order: Order) -> bool:
    """Hủy đơn và hoàn lại tồn kho. Trả False nếu đơn đã hủy từ trước.

    Khóa dòng sản phẩm (SELECT ... FOR UPDATE trên MySQL) giống lúc đặt hàng để
    hai instance cùng hủy/đặt một sản phẩm không làm sai số tồn kho.
    Người gọi chịu trách nhiệm commit.
    """
    if order.status == CANCELLED:
        return False
    qty = {}
    for it in order.items:
        qty[it.product_id] = qty.get(it.product_id, 0) + it.quantity
    if qty:
        for p in db.scalars(select(Product).where(Product.id.in_(list(qty))).with_for_update()).all():
            p.stock += qty[p.id]
    order.status = CANCELLED
    return True
