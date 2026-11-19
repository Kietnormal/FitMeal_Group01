from django.conf import settings


def shop_settings(request):
    return {"shipping_fees_enabled": settings.SHIPPING_FEES_ENABLED}
