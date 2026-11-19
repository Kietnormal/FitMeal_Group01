import re
import unicodedata
from decimal import Decimal

from django.conf import settings

from apps.products.models import Product

FREE_SHIPPING_THRESHOLD = Decimal("300000.00")
LOCAL_STANDARD_SHIPPING_FEE = Decimal("20000.00")
DRY_GOODS_LOCAL_BASE_FEE = Decimal("20000.00")
DRY_GOODS_NATIONWIDE_BASE_FEE = Decimal("30000.00")
DRY_GOODS_LOCAL_INCREMENTAL_FEE = Decimal("5000.00")
DRY_GOODS_NATIONWIDE_INCREMENTAL_FEE = Decimal("10000.00")


def normalize_location(value):
    value = value.strip().lower().replace("đ", "d")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]", "", value)


def is_ho_chi_minh_city(value):
    return normalize_location(value) in {
        "hcm",
        "tphcm",
        "tphochiminh",
        "hochiminh",
        "thanhphohochiminh",
        "saigon",
        "thanhphosaigon",
        "hochiminhcity",
    }


def calculate_dry_goods_shipping(total_weight_grams, destination_city):
    if total_weight_grams < 1:
        raise ValueError("Đồ khô cần khối lượng lớn hơn 0 g để tính phí vận chuyển.")
    is_local = is_ho_chi_minh_city(destination_city)
    base_fee = (
        DRY_GOODS_LOCAL_BASE_FEE if is_local else DRY_GOODS_NATIONWIDE_BASE_FEE
    )
    incremental_fee = (
        DRY_GOODS_LOCAL_INCREMENTAL_FEE
        if is_local
        else DRY_GOODS_NATIONWIDE_INCREMENTAL_FEE
    )
    additional_half_kilograms = max(0, (total_weight_grams - 1000 + 499) // 500)
    return base_fee + incremental_fee * additional_half_kilograms


def calculate_order_shipping(subtotal, quantities, products, destination_city):
    if not settings.SHIPPING_FEES_ENABLED:
        return Decimal("0.00")
    items = [products[slug] for slug in quantities]
    dry_goods_only = all(product.category == Product.Category.DRY_GOODS for product in items)
    has_dry_goods = any(product.category == Product.Category.DRY_GOODS for product in items)

    if has_dry_goods and any(product.shipping_weight_grams < 1 for product in items if product.category == Product.Category.DRY_GOODS):
        raise ValueError("Vui lòng cập nhật khối lượng giao hàng cho sản phẩm đồ khô.")

    if dry_goods_only:
        total_weight = sum(
            products[slug].shipping_weight_grams * quantity
            for slug, quantity in quantities.items()
        )
        return calculate_dry_goods_shipping(total_weight, destination_city)

    if subtotal >= FREE_SHIPPING_THRESHOLD:
        return Decimal("0.00")
    return LOCAL_STANDARD_SHIPPING_FEE
