from datetime import timedelta
import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone


def validate_avatar_size(image):
    if image.size > 1024 * 1024:
        raise ValidationError("Ảnh đại diện không được lớn hơn 1 MB.")


def email_change_expiry():
    return timezone.now() + timedelta(days=1)


class User(AbstractUser):
    """Khách hàng và nhân viên dùng chung model; is_staff controls admin-site access."""

    class StaffRole(models.TextChoices):
        ADMIN = "admin", "Quản trị viên"
        MANAGER = "manager", "Quản lý"
        SALES = "sales", "NV bán hàng"

    class Gender(models.TextChoices):
        UNSPECIFIED = "unspecified", "Chưa chọn"
        MALE = "male", "Nam"
        FEMALE = "female", "Nữ"
        OTHER = "other", "Khác"

    phone = models.CharField("Số điện thoại", max_length=15, blank=True)
    cccd = models.CharField("Số CCCD", max_length=12, null=True, blank=True, unique=True)
    staff_role = models.CharField(
        "Vai trò nhân viên",
        max_length=12,
        choices=StaffRole.choices,
        blank=True,
        default="",
    )
    address = models.CharField("Địa chỉ giao hàng", max_length=250, blank=True)
    phone_verified = models.BooleanField("Đã xác minh số điện thoại", default=False)
    must_change_password = models.BooleanField("Phải đổi mật khẩu", default=False)
    gender = models.CharField(
        "Giới tính",
        max_length=12,
        choices=Gender.choices,
        default=Gender.UNSPECIFIED,
    )
    birth_date = models.DateField("Ngày sinh", null=True, blank=True)
    avatar = models.ImageField(
        "Ảnh đại diện",
        upload_to="users/avatars/",
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png"]), validate_avatar_size],
    )

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.staff_role = self.StaffRole.ADMIN
        super().save(*args, **kwargs)

    @property
    def masked_phone(self):
        digits = "".join(character for character in self.phone if character.isdigit())
        return f"{'*' * max(len(digits) - 3, 0)}{digits[-3:]}" if digits else "—"


class CustomerAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_addresses")
    label = models.CharField("Tên địa chỉ", max_length=50, default="Nhà")
    address = models.CharField("Địa chỉ", max_length=250)
    district = models.CharField("Quận / Huyện", max_length=100)
    city = models.CharField("Tỉnh / Thành phố", max_length=100)
    is_default = models.BooleanField("Địa chỉ mặc định", default=False)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "created_at", "pk"]
        verbose_name = "Địa chỉ khách hàng"
        verbose_name_plural = "Địa chỉ khách hàng"

    def __str__(self):
        return f"{self.label}: {self.address}, {self.district}, {self.city}"


class PointsTransaction(models.Model):
    class Kind(models.TextChoices):
        EARNED = "earned", "Tích điểm"
        REVERSAL = "reversal", "Điều chỉnh đơn hủy"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="points_transactions")
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="points_transactions",
    )
    kind = models.CharField("Loại giao dịch", max_length=12, choices=Kind.choices)
    points = models.IntegerField("Điểm", help_text="Có thể âm khi hoàn điểm.")
    description = models.CharField("Nội dung", max_length=200)
    created_at = models.DateTimeField("Ngày ghi nhận", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["order", "kind"], name="accounts_unique_order_points_kind"),
        ]
        verbose_name = "Giao dịch điểm"
        verbose_name_plural = "Giao dịch điểm"

    def __str__(self):
        return f"{self.user} {self.points:+} điểm"


class OrderReview(models.Model):
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="customer_review",
    )
    rating = models.PositiveSmallIntegerField(
        "Đánh giá",
        choices=[(value, f"{value} sao") for value in range(1, 6)],
    )
    comment = models.TextField("Nhận xét", blank=True, max_length=1000)
    created_at = models.DateTimeField("Ngày đánh giá", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật lần cuối", auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-pk"]
        verbose_name = "Đánh giá đơn hàng"
        verbose_name_plural = "Đánh giá đơn hàng"

    def __str__(self):
        return f"{self.order.order_number}: {self.rating}/5"


class PendingEmailChange(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="pending_email_change")
    email = models.EmailField("Email mới")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=email_change_expiry)

    class Meta:
        verbose_name = "Yêu cầu đổi email"
        verbose_name_plural = "Yêu cầu đổi email"

    def __str__(self):
        return f"{self.user} → {self.email}"


class LoginEvent(models.Model):
    class Outcome(models.TextChoices):
        SUCCESS = "success", "Thành công"
        FAILURE = "failure", "Sai thông tin"
        BLOCKED = "blocked", "Bị chặn"

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_events",
    )
    login_identifier = models.CharField(max_length=254, blank=True)
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    details = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "Sự kiện đăng nhập"
        verbose_name_plural = "Sự kiện đăng nhập"

    def __str__(self):
        return f"{self.login_identifier or self.user} · {self.get_outcome_display()}"


class LoginThrottle(models.Model):
    ip_address = models.CharField(max_length=45, unique=True)
    failure_count = models.PositiveSmallIntegerField(default=0)
    window_started_at = models.DateTimeField(default=timezone.now)
    blocked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Giới hạn đăng nhập theo IP"
        verbose_name_plural = "Giới hạn đăng nhập theo IP"

    def __str__(self):
        return self.ip_address


class SecurityPolicy(models.Model):
    require_admin_2fa = models.BooleanField("Bắt buộc 2FA với quản trị viên", default=False)
    require_manager_2fa = models.BooleanField("Bắt buộc 2FA với quản lý", default=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_policy_updates",
    )

    class Meta:
        verbose_name = "Chính sách bảo mật"
        verbose_name_plural = "Chính sách bảo mật"

    def __str__(self):
        return "Chính sách xác thực nhân viên"
