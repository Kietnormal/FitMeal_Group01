from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_ref",
        "order",
        "amount",
        "status",
        "response_code",
        "expires_at",
        "paid_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("transaction_ref", "order__order_number")
    readonly_fields = tuple(field.name for field in PaymentTransaction._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
