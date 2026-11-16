from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    CustomerAddress,
    LoginEvent,
    LoginThrottle,
    OrderReview,
    PendingEmailChange,
    PointsTransaction,
    User,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Thông tin liên hệ", {"fields": ("phone", "phone_verified", "address")}),
        ("Bảo mật", {"fields": ("must_change_password",)}),
        ("Hồ sơ khách hàng", {"fields": ("gender", "birth_date", "avatar")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (("Thông tin liên hệ", {"fields": ("phone", "address")}),)
    list_display = ("username", "email", "phone", "is_staff", "is_superuser", "must_change_password")


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "address", "district", "city", "is_default")
    list_filter = ("is_default", "city")
    search_fields = ("user__email", "user__phone", "address", "district", "city")


@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "points", "order", "created_at")
    list_filter = ("kind", "created_at")
    search_fields = ("user__email", "user__phone", "order__order_number")
    readonly_fields = ("user", "order", "kind", "points", "description", "created_at")

    def has_add_permission(self, request):
        return False


@admin.register(OrderReview)
class OrderReviewAdmin(admin.ModelAdmin):
    list_display = ("order", "rating", "created_at", "updated_at")
    list_filter = ("rating", "created_at")
    search_fields = ("order__order_number", "order__customer__email", "comment")
    readonly_fields = ("order", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False


@admin.register(PendingEmailChange)
class PendingEmailChangeAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "created_at", "expires_at")
    readonly_fields = ("user", "email", "token", "created_at", "expires_at")

    def has_add_permission(self, request):
        return False


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "login_identifier", "ip_address", "outcome", "details")
    list_filter = ("outcome", "created_at")
    search_fields = ("login_identifier", "ip_address")
    readonly_fields = tuple(field.name for field in LoginEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LoginThrottle)
class LoginThrottleAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "failure_count", "window_started_at", "blocked_until")
    readonly_fields = tuple(field.name for field in LoginThrottle._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
