from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    DeliveryIssue,
    Order,
    OrderCareRequest,
    OrderCancellationRequest,
    OrderItem,
    OrderPiiAccessLog,
)


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
        "customer_pii_purged_at",
        "customer_pii_access_link",
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
            (
                "Quyền riêng tư",
                {
                    "fields": (
                        "customer_information_redacted",
                        "customer_pii_purged_at",
                        "customer_pii_access_link",
                    )
                },
            ),
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
        return "Đã mã hóa và ẩn theo chính sách thời hạn lưu trữ."

    @admin.display(description="Mở dữ liệu có ghi nhật ký")
    def customer_pii_access_link(self, obj):
        if obj.customer_pii_purged_at:
            return "Dữ liệu định danh đã được xóa."
        if obj.customer_care_period_open:
            return "Trong thời hạn 7 ngày; chỉ xem khi xử lý khiếu nại."
        if obj.can_request_pii_access():
            return format_html(
                '<a href="{}">Nhập lý do để mở thông tin</a>',
                reverse("staff_orders:access_order_pii", args=[obj.pk]),
            )
        return "Thông tin cá nhân không còn khả dụng."

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


@admin.register(OrderCareRequest)
class OrderCareRequestAdmin(admin.ModelAdmin):
    list_display = ("order", "request_type", "status", "requested_at", "resolved_by", "resolved_at")
    list_filter = ("request_type", "status", "requested_at")
    search_fields = ("order__order_number", "details", "resolution_note")
    readonly_fields = tuple(field.name for field in OrderCareRequest._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderPiiAccessLog)
class OrderPiiAccessLogAdmin(admin.ModelAdmin):
    list_display = ("order", "accessed_by", "reason", "accessed_at")
    list_filter = ("accessed_at",)
    search_fields = ("order__order_number", "accessed_by__username", "reason")
    readonly_fields = tuple(field.name for field in OrderPiiAccessLog._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
