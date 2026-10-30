from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Người dùng của hệ thống. Khách hàng và quản trị dùng chung model, phân biệt bằng is_staff."""

    phone = models.CharField("Số điện thoại", max_length=15, blank=True)

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"
