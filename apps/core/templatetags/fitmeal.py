from decimal import Decimal

from django import template
from django.templatetags.static import static

register = template.Library()

FALLBACK_CATEGORIES = {"meal", "rice", "salad", "drink", "snack", "combo", "dry_goods"}
ENERGY_PER_GRAM = {"protein": 4, "carbs": 4, "fat": 9}


@register.filter
def food_image(product):
    """Return the product photo, or a category photo while the shop has none."""
    if getattr(product, "image", None):
        return product.image.url
    category = getattr(product, "category", "")
    return static(f"img/food/{category if category in FALLBACK_CATEGORIES else 'meal'}.webp")


@register.simple_tag
def energy_share(product, nutrient):
    """Share of a serving's calories that comes from one macronutrient, in percent."""
    calories = Decimal(getattr(product, "calories", 0) or 0)
    grams = Decimal(getattr(product, nutrient, 0) or 0)
    if calories <= 0 or nutrient not in ENERGY_PER_GRAM:
        return 0
    return min(100, round(grams * ENERGY_PER_GRAM[nutrient] * 100 / calories))


@register.filter
def vnd(value):
    """Format a price the Vietnamese way: 129000 -> 129.000₫."""
    try:
        amount = round(Decimal(value))
    except (TypeError, ValueError, ArithmeticError):
        return value
    return f"{amount:,}".replace(",", ".") + "₫"
