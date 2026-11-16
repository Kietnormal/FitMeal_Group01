from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("account/actions/", include("apps.accounts.urls")),
    path("api/products/", include("apps.products.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("payments/", include("apps.payments.urls")),
    path("management/orders/", include("apps.orders.staff_urls")),
    path("", include("apps.core.urls")),
]

# Chỉ phục vụ file upload qua Django khi phát triển; server thật dùng Nginx
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
