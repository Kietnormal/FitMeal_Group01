from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import Product


def serialize_product(product, request):
    return {
        "id": product.slug,
        "slug": product.slug,
        "sku": product.sku,
        "name": product.name,
        "category": product.category,
        "description": product.description,
        "price": str(product.price),
        "shipping_weight_grams": product.shipping_weight_grams,
        "expiry_date": product.expiry_date.isoformat() if product.expiry_date else "",
        "image": request.build_absolute_uri(product.image.url) if product.image else "",
        "available": product.is_available
        and (not product.tracks_inventory or product.stock_quantity is not None),
        "featured": product.is_featured,
        "calories": product.calories,
        "protein": str(product.protein),
        "carbs": str(product.carbs),
        "fat": str(product.fat),
        "ingredients": product.ingredients,
        "allergens": product.allergens,
        "serving": product.serving,
    }


@require_GET
def product_list(request):
    products = Product.objects.all()
    results = [serialize_product(product, request) for product in products]
    return JsonResponse({"count": len(results), "results": results})


@require_GET
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    return JsonResponse(serialize_product(product, request))
