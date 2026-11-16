from django.contrib import admin

from .models import DeliveryIssue, Order, OrderCancellationRequest, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product",
        "product_sku",
        "product_name",
        "unit_price",
        "quantity",
        "line_total",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer_name_display",
        "customer_phone_display",
        "status",
        "total",
        "delivery_date",
        "created_at",
    )
    list_filter = ("status", "payment_method", "delivery_date", "created_at")
    search_fields = ("order_number", "customer_name", "customer_email", "customer_phone")
    readonly_fields = (
        "order_number",
        "tracking_token",
        "status",
        "cancelled_at",
        "cancelled_by",
        "cancellation_reason",
        "refund_status",
        "created_at",
        "updated_at",
    )
    inlines = (OrderItemInline,)
    ordering = ("-created_at",)
    fieldsets = (
        ("Đơn hàng", {"fields": ("order_number", "tracking_token", "status", "created_at", "updated_at")}),
        ("Thông tin khách hàng", {"fields": ("customer", "customer_name", "customer_email", "customer_phone")}),
        ("Giao hàng", {"fields": ("address", "district", "city", "delivery_date", "delivery_slot", "note")}),
        ("Thanh toán", {"fields": ("payment_method", "subtotal", "shipping_fee", "total")}),
        ("Hủy và hoàn tiền", {"fields": ("cancelled_at", "cancelled_by", "cancellation_reason", "refund_status")}),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj or not obj.customer_info_redacted:
            return fieldsets
        visible_fieldsets = [
            fieldset
            for fieldset in fieldsets
            if fieldset[0] not in {"Thông tin khách hàng", "Giao hàng"}
        ]
        visible_fieldsets.insert(
            1,
            ("Quyền riêng tư", {"fields": ("customer_information_redacted",)}),
        )
        return visible_fieldsets

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj and obj.customer_info_redacted:
            return (*readonly_fields, "customer_information_redacted")
        return readonly_fields

    @admin.display(description="Khách hàng")
    def customer_name_display(self, obj):
        return "Đã ẩn sau khi đơn kết thúc" if obj.customer_info_redacted else obj.customer_name

    @admin.display(description="Số điện thoại")
    def customer_phone_display(self, obj):
        return "Đã ẩn" if obj.customer_info_redacted else obj.customer_phone

    @admin.display(description="Thông tin cá nhân")
    def customer_information_redacted(self, obj):
        return "Đã mã hóa và ẩn sau khi đơn hoàn tất hoặc bị hủy."

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(OrderCancellationRequest)
class OrderCancellationRequestAdmin(admin.ModelAdmin):
    list_display = ("order", "source", "status", "contact_outcome", "contact_attempts", "requested_at")
    list_filter = ("source", "status", "contact_outcome")
    search_fields = ("order__order_number", "order__customer_name", "reason")
    readonly_fields = tuple(field.name for field in OrderCancellationRequest._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DeliveryIssue)
class DeliveryIssueAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "reported_at", "resolved_by", "resolved_at")
    list_filter = ("status", "resolution_outcome", "reported_at")
    search_fields = ("order__order_number", "details", "resolution")
    readonly_fields = tuple(field.name for field in DeliveryIssue._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
