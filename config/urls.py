from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

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

# Chỉ bật phục vụ ảnh sản phẩm qua Django cho demo cô lập khi được cấu hình rõ ràng.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_PRODUCT_MEDIA:
    urlpatterns += [
        re_path(
            r"^media/products/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT / "products"},
        )
    ]

if getattr(settings, "SERVE_DEMO_STATIC", False):
    urlpatterns += [
        re_path(
            r"^static/(?P<path>.*)$",
            serve,
            {"document_root": settings.STATIC_ROOT},
        )
    ]
