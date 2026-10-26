from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Thông tin thêm", {"fields": ("phone",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Thông tin thêm", {"fields": ("phone",)}),)
    list_display = ("username", "email", "phone", "is_staff")
