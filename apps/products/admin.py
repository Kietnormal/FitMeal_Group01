from django.contrib import admin

from .models import Product, ProductActivity
from .services import record_product_activity


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "category",
        "price",
        "inventory_display",
        "low_stock_threshold",
        "is_available",
        "is_featured",
    )
    list_filter = ("category", "is_available", "is_featured")
    list_editable = ("price", "is_available", "is_featured")
    search_fields = ("name", "sku", "description", "ingredients")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)
    fieldsets = (
        ("Thông tin sản phẩm", {"fields": ("name", "slug", "sku", "category", "description")}),
        ("Giá và hiển thị", {"fields": ("price", "image", "is_available", "is_featured")}),
        ("Giao hàng đồ khô", {"fields": ("shipping_weight_grams", "expiry_date")}),
        (
            "Thông tin dinh dưỡng",
            {"fields": ("calories", "protein", "carbs", "fat", "serving")},
        ),
        ("Tồn kho (chỉ đồ khô)", {"fields": ("stock_quantity", "low_stock_threshold")}),
        ("Thành phần và dị ứng", {"fields": ("ingredients", "allergens")}),
        ("Thời gian", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Tồn kho")
    def inventory_display(self, obj):
        if not obj.tracks_inventory:
            return "Làm sau khi đặt"
        if obj.stock_quantity is None:
            return "Chưa nhập"
        return obj.stock_quantity

    def save_model(self, request, obj, form, change):
        previous = (
            Product.objects.get(pk=obj.pk)
            if change and obj.pk
            else None
        )
        super().save_model(request, obj, form, change)
        if previous is None:
            record_product_activity(
                product=obj,
                actor=request.user,
                action=ProductActivity.Action.CREATED,
                new_value=format(obj.price, ".2f"),
            )
            if obj.tracks_inventory and obj.stock_quantity is not None:
                record_product_activity(
                    product=obj,
                    actor=request.user,
                    action=ProductActivity.Action.INVENTORY_CHANGED,
                    new_value=(
                        f"{obj.stock_quantity} · ngưỡng {obj.low_stock_threshold}"
                    ),
                )
            return

        if previous.price != obj.price:
            record_product_activity(
                product=obj,
                actor=request.user,
                action=ProductActivity.Action.PRICE_CHANGED,
                old_value=format(previous.price, ".2f"),
                new_value=format(obj.price, ".2f"),
            )
        if obj.tracks_inventory and (
            previous.stock_quantity != obj.stock_quantity
            or previous.low_stock_threshold != obj.low_stock_threshold
        ):
            old_stock = (
                "Chưa cập nhật"
                if previous.stock_quantity is None
                else str(previous.stock_quantity)
            )
            new_stock = (
                "Chưa cập nhật" if obj.stock_quantity is None else str(obj.stock_quantity)
            )
            record_product_activity(
                product=obj,
                actor=request.user,
                action=ProductActivity.Action.INVENTORY_CHANGED,
                old_value=f"{old_stock} · ngưỡng {previous.low_stock_threshold}",
                new_value=f"{new_stock} · ngưỡng {obj.low_stock_threshold}",
            )
        if previous.is_available != obj.is_available:
            record_product_activity(
                product=obj,
                actor=request.user,
                action=ProductActivity.Action.AVAILABILITY_CHANGED,
                old_value="Đang bán" if previous.is_available else "Tạm ngưng",
                new_value="Đang bán" if obj.is_available else "Tạm ngưng",
            )


@admin.register(ProductActivity)
class ProductActivityAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_display", "action", "product_name", "product_sku")
    list_display_links = None
    list_filter = ("action", "created_at")
    search_fields = ("product_name", "product_sku", "actor__username", "actor__email")
    readonly_fields = (
        "product",
        "product_name",
        "product_sku",
        "actor",
        "action",
        "old_value",
        "new_value",
        "created_at",
    )
    ordering = ("-created_at", "-pk")

    @admin.display(description="Người thực hiện")
    def actor_display(self, obj):
        if not obj.actor_id:
            return "Quản trị hệ thống"
        return obj.actor.get_full_name() or obj.actor.username

    def has_add_permission(self, request):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
