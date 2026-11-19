"""Data for the "Thanh toán thành công" page shown once an online payment is confirmed."""

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order
from apps.products.models import Product

STORE_CONTACT_EMAIL = "hello@fitmeal.vn"

# Order statuses grouped by how far the order has moved through the four steps
# shown on the page: paid -> store confirmed -> preparing -> delivering.
_CONFIRMED = {Order.Status.CONFIRMED}
_PREPARING = {Order.Status.PREPARING, Order.Status.PACKING}
_READY = {Order.Status.READY}
_DELIVERING = {
    Order.Status.SHIPPED,
    Order.Status.DELIVERING,
    Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
    Order.Status.DELIVERY_ISSUE,
}
_DELIVERED = {Order.Status.DELIVERED}


def _completed_steps(order_status):
    """How many of the four steps are finished (payment is always finished)."""
    if order_status in _DELIVERED:
        return 4
    if order_status in _DELIVERING or order_status in _READY:
        return 3
    if order_status in _PREPARING or order_status in _CONFIRMED:
        return 2
    return 1


def _relative_day(value):
    today = timezone.localdate()
    if value == today:
        return "hôm nay"
    if value == today + timedelta(days=1):
        return "ngày mai"
    return value.strftime("%d/%m/%Y")


def _delivery_text(order):
    if order.delivery_slot == Order.DeliverySlot.COURIER:
        return "Đơn vị vận chuyển sắp xếp"
    return f"{order.delivery_slot} {_relative_day(order.delivery_date)}"


def _item_lines(order, request):
    lines = []
    for item in order.items.select_related("product"):
        product = item.product
        is_dry = item.product_category == Product.Category.DRY_GOODS
        meta = ["Đồ khô" if is_dry else "Đồ tươi"]
        if product and product.calories:
            meta.append(f"{product.calories} kcal")
        meta.append(f"SL {item.quantity}")
        if is_dry:
            icon = "fm-box"
        elif item.product_category == Product.Category.DRINK:
            icon = "fm-cup"
        else:
            icon = "fm-flame"
        lines.append(
            {
                "name": item.product_name,
                "meta": " · ".join(meta),
                "line_total": item.line_total,
                "image_url": product.image.url if product and product.image else "",
                "icon": icon,
            }
        )
    return lines


def order_complete_context(request, payment, *, order_url):
    order = payment.order
    paid_at = timezone.localtime(payment.paid_at or payment.updated_at)
    completed = _completed_steps(order.status)
    delivery_text = _delivery_text(order)
    step_definitions = [
        ("Đã thanh toán", f"{paid_at:%H:%M} {_relative_day(paid_at.date())}"),
        ("Cửa hàng xác nhận", "Thường trong 5–10 phút"),
        ("Đang chuẩn bị", "Chuẩn bị theo đơn"),
        ("Đang giao", f"Khung {delivery_text}"),
    ]
    steps = []
    for index, (title, detail) in enumerate(step_definitions, start=1):
        if index <= completed:
            state = "done"
        elif index == completed + 1:
            state = "current"
        else:
            state = "upcoming"
        steps.append({"number": index, "title": title, "detail": detail, "state": state})

    if order.customer_pii_purged_at:
        address = "Đã ẩn để bảo vệ thông tin khách hàng"
    else:
        address = ", ".join(part for part in (order.address, order.district, order.city) if part)

    return {
        "payment": payment,
        "order": order,
        "provider_label": payment.get_provider_display(),
        "paid_at": paid_at,
        "lines": _item_lines(order, request),
        "steps": steps,
        "order_cancelled": order.status == Order.Status.CANCELLED,
        "delivery_text": delivery_text,
        "address": address,
        "order_url": order_url,
        "cart_url": reverse("core:cart"),
        "store_contact_email": STORE_CONTACT_EMAIL,
    }
