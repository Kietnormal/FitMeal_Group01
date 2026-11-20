import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.db import DEFAULT_DB_ALIAS, transaction

from apps.products.models import Product
from .privacy import (
    CUSTOMER_CARE_PERIOD,
    ORDER_PII_RETENTION_PERIOD,
    ORDER_REDACTED_FIELDS,
    build_order_pii_snapshot,
    encrypt_order_pii_snapshot,
)


def generate_order_number():
    return f"FM-{timezone.localdate():%Y}-{uuid.uuid4().hex[:8].upper()}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Chờ xác nhận"
        CONFIRMED = "confirmed", "Đã xác nhận"
        PREPARING = "preparing", "Đang chuẩn bị"
        PACKING = "packing", "Đang đóng gói"
        READY = "ready", "Sẵn sàng giao"
        SHIPPED = "shipped", "Đã giao cho đơn vị vận chuyển"
        DELIVERING = "delivering", "Đang giao"
        AWAITING_CUSTOMER_CONFIRMATION = "awaiting_confirmation", "Chờ khách xác nhận đã nhận"
        DELIVERY_ISSUE = "delivery_issue", "Đang khiếu nại giao hàng"
        DELIVERED = "delivered", "Hoàn tất"
        CANCELLED = "cancelled", "Đã hủy"

    class DeliverySlot(models.TextChoices):
        MORNING = "08:00–10:00", "08:00–10:00"
        LATE_MORNING = "10:00–12:00", "10:00–12:00"
        EARLY_AFTERNOON = "12:00–14:00", "12:00–14:00"
        AFTERNOON = "14:00–16:00", "14:00–16:00"
        LATE_AFTERNOON = "16:00–18:00", "16:00–18:00"
        EVENING = "18:00–20:00", "18:00–20:00"
        COURIER = "courier", "Đơn vị vận chuyển tự sắp xếp"

    class DeliveryConfirmationMethod(models.TextChoices):
        CUSTOMER = "customer", "Khách xác nhận"
        AUTOMATIC = "automatic", "Tự xác nhận sau thời hạn"
        MANAGER = "manager", "Quản lý xác nhận"

    class DeliveryRegion(models.TextChoices):
        HO_CHI_MINH_CITY = "hcm", "TP. Hồ Chí Minh"
        OTHER_PROVINCES = "other", "Các tỉnh khác"

    class CancellationReasonCategory(models.TextChoices):
        CUSTOMER_CHANGED_MIND = "changed_mind", "Khách đổi ý"
        OUT_OF_STOCK = "out_of_stock", "Hết món"
        NO_CONTACT = "no_contact", "Không liên lạc được"
        PAYMENT_EXPIRED = "payment_expired", "Thanh toán hết hạn"
        OTHER = "other", "Lý do khác"

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Chuyển khoản ngân hàng"
        COD = "cod", "Thanh toán khi nhận hàng (COD)"
        VNPAY = "vnpay", "VNPay (đơn cũ)"

    class RefundStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Không cần hoàn tiền"
        REQUESTED = "requested", "Chờ hoàn tiền"
        REFUNDED = "refunded", "Đã hoàn tiền"
        FAILED = "failed", "Hoàn tiền lỗi"

    order_number = models.CharField(max_length=20, unique=True, default=generate_order_number)
    tracking_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    customer_name = models.CharField("Người nhận", max_length=120)
    customer_email = models.EmailField("Email")
    customer_phone = models.CharField("Số điện thoại", max_length=20)
    address = models.CharField("Địa chỉ", max_length=250)
    district = models.CharField("Quận / Huyện", max_length=100)
    city = models.CharField("Tỉnh / Thành phố", max_length=100)
    delivery_region = models.CharField(
        "Khu vực giao hàng",
        max_length=8,
        choices=DeliveryRegion.choices,
        blank=True,
    )
    customer_pii_encrypted = models.TextField(
        "Thông tin khách hàng đã mã hóa",
        blank=True,
        editable=False,
    )
    customer_pii_purged_at = models.DateTimeField(
        "Thời điểm xóa dữ liệu cá nhân",
        null=True,
        blank=True,
        editable=False,
    )
    delivery_date = models.DateField("Ngày giao")
    delivery_slot = models.CharField("Khung giờ giao", max_length=20, choices=DeliverySlot.choices)
    note = models.TextField("Ghi chú", blank=True)
    payment_method = models.CharField(
        "Phương thức thanh toán",
        max_length=16,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
    )
    status = models.CharField(
        "Trạng thái",
        max_length=24,
        choices=Status.choices,
        default=Status.PENDING,
    )
    delivery_confirmation_deadline = models.DateTimeField(
        "Hạn xác nhận đã nhận hàng",
        null=True,
        blank=True,
    )
    delivery_confirmed_at = models.DateTimeField("Thời điểm xác nhận đã nhận", null=True, blank=True)
    delivery_confirmation_method = models.CharField(
        "Cách xác nhận đã nhận",
        max_length=12,
        choices=DeliveryConfirmationMethod.choices,
        blank=True,
    )
    cancelled_at = models.DateTimeField("Thời điểm hủy", null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_orders",
    )
    cancellation_reason = models.TextField("Lý do hủy", blank=True, max_length=1000)
    cancellation_reason_category = models.CharField(
        "Nhóm lý do hủy",
        max_length=20,
        choices=CancellationReasonCategory.choices,
        blank=True,
    )
    refund_status = models.CharField(
        "Trạng thái hoàn tiền",
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.NOT_REQUIRED,
    )
    subtotal = models.DecimalField(
        "Tạm tính", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)]
    )
    shipping_fee = models.DecimalField(
        "Phí giao hàng", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(
        "Tổng tiền", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField("Ngày đặt", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật lần cuối", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Đơn hàng"
        verbose_name_plural = "Đơn hàng"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["customer", "created_at"]),
            models.Index(
                fields=["status", "delivery_confirmation_deadline"],
                name="orders_due_conf_idx",
            ),
        ]

    def __str__(self):
        return self.order_number

    @property
    def customer_info_redacted(self):
        return bool(self.customer_pii_encrypted or self.customer_pii_purged_at)

    @property
    def customer_care_deadline(self):
        if self.status != self.Status.DELIVERED:
            return None
        delivered_at = self.delivery_confirmed_at or self.updated_at or self.created_at
        return delivered_at + CUSTOMER_CARE_PERIOD if delivered_at else None

    def can_submit_customer_care_request(self, now=None):
        deadline = self.customer_care_deadline
        return bool(
            deadline
            and (now or timezone.now()) <= deadline
            and self.status == self.Status.DELIVERED
        )

    @property
    def customer_care_period_open(self):
        return self.can_submit_customer_care_request()

    @property
    def customer_pii_retention_deadline(self):
        if self.status == self.Status.DELIVERED:
            anchor = self.delivery_confirmed_at or self.updated_at or self.created_at
        elif self.status == self.Status.CANCELLED:
            anchor = self.cancelled_at or self.updated_at or self.created_at
        else:
            return None
        return anchor + ORDER_PII_RETENTION_PERIOD if anchor else None

    def customer_pii_retention_expired(self, now=None):
        deadline = self.customer_pii_retention_deadline
        return bool(deadline and deadline <= (now or timezone.now()))

    def can_request_pii_access(self, now=None):
        now = now or timezone.now()
        return bool(
            self.customer_pii_encrypted
            and not self.customer_pii_purged_at
            and not self.can_submit_customer_care_request(now)
            and not self.customer_pii_retention_expired(now)
        )

    @property
    def is_dry_goods_order(self):
        items = list(self.items.all())
        return bool(items) and all(
            item.product_category == Product.Category.DRY_GOODS for item in items
        )

    def save(self, *args, **kwargs):
        if self.customer_pii_purged_at:
            for field in ORDER_REDACTED_FIELDS:
                setattr(self, field, "")
            self.customer_pii_encrypted = ""
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {
                    *ORDER_REDACTED_FIELDS,
                    "customer_pii_encrypted",
                }
            return super().save(*args, **kwargs)

        should_redact = self.status in {
            self.Status.DELIVERED,
            self.Status.CANCELLED,
        } or bool(self.customer_pii_encrypted)
        if not should_redact:
            return super().save(*args, **kwargs)

        requests = list(self.cancellation_requests.all()) if self.pk and not self.customer_pii_encrypted else []
        delivery_issues = (
            list(self.delivery_issues.all())
            if self.pk and not self.customer_pii_encrypted
            else []
        )
        if not self.customer_pii_encrypted:
            self.customer_pii_encrypted = encrypt_order_pii_snapshot(
                build_order_pii_snapshot(self, requests, delivery_issues)
            )
        self.delivery_confirmation_deadline = None
        for field in ORDER_REDACTED_FIELDS:
            setattr(self, field, "")

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                *ORDER_REDACTED_FIELDS,
                "customer_pii_encrypted",
                "delivery_confirmation_deadline",
                "updated_at",
            }

        using = kwargs.get("using") or self._state.db or DEFAULT_DB_ALIAS
        with transaction.atomic(using=using):
            super().save(*args, **kwargs)
            for cancellation in requests:
                cancellation.reason = ""
                cancellation.contact_notes = ""
                cancellation.manager_resolution_reason = ""
                fields = ["reason", "contact_notes", "manager_resolution_reason"]
                if cancellation.source == OrderCancellationRequest.Source.CUSTOMER:
                    cancellation.requested_by = None
                    fields.append("requested_by")
                cancellation.save(using=using, update_fields=fields)
            for issue in delivery_issues:
                issue.details = ""
                issue.resolution = ""
                issue.reported_by = None
                issue.save(
                    using=using,
                    update_fields=["details", "resolution", "reported_by"],
                )


class DeliveryIssue(models.Model):
    class Source(models.TextChoices):
        CUSTOMER = "customer", "Khách hàng"
        STAFF_DELIVERY = "staff_delivery", "Nhân viên giao hàng"

    class Status(models.TextChoices):
        PENDING = "pending", "Chờ quản lý xử lý"
        RESOLVED = "resolved", "Đã xử lý"

    class Resolution(models.TextChoices):
        CONFIRMED = "confirmed", "Xác nhận khách đã nhận"
        REDELIVER = "redeliver", "Tiếp tục giao hàng"
        CONTACTED = "contacted", "Đã liên hệ, tiếp tục giao"
        CANCELLED = "cancelled", "Hủy đơn do giao thất bại"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="delivery_issues")
    source = models.CharField(
        "Nguồn ghi nhận",
        max_length=16,
        choices=Source.choices,
        default=Source.CUSTOMER,
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    details = models.TextField("Nội dung khiếu nại", max_length=1000)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_issues",
    )
    reported_at = models.DateTimeField("Thời điểm khiếu nại", auto_now_add=True)
    resolution = models.TextField("Ghi chú xử lý", blank=True, max_length=1000)
    resolution_outcome = models.CharField(
        "Kết quả xử lý",
        max_length=12,
        choices=Resolution.choices,
        blank=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_delivery_issues",
    )
    resolved_at = models.DateTimeField("Thời điểm xử lý", null=True, blank=True)

    class Meta:
        ordering = ["-reported_at", "-pk"]
        indexes = [models.Index(fields=["status", "reported_at"])]
        verbose_name = "Khiếu nại giao hàng"
        verbose_name_plural = "Khiếu nại giao hàng"

    def __str__(self):
        return f"{self.order.order_number} · {self.get_status_display()}"


class OrderCancellationRequest(models.Model):
    class Source(models.TextChoices):
        CUSTOMER = "customer", "Khách hàng"
        STAFF = "staff", "Nhân viên"

    class Status(models.TextChoices):
        CONTACT_PENDING = "contact_pending", "Chờ nhân viên liên hệ"
        MANAGER_REVIEW = "manager_review", "Chờ quản lý duyệt"
        APPROVED = "approved", "Đã duyệt hủy"
        REJECTED = "rejected", "Đã từ chối"
        WITHDRAWN = "withdrawn", "Khách tiếp tục nhận đơn"

    class ContactOutcome(models.TextChoices):
        NOT_REQUIRED = "not_required", "Không cần liên hệ"
        AGREED_TO_CONTINUE = "agreed_to_continue", "Đồng ý nhận tiếp"
        STILL_WANTS_CANCEL = "still_wants_cancel", "Vẫn muốn hủy"
        NO_ANSWER = "no_answer", "Không liên lạc được"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="cancellation_requests",
    )
    source = models.CharField("Nguồn yêu cầu", max_length=12, choices=Source.choices)
    status = models.CharField(
        "Trạng thái yêu cầu",
        max_length=20,
        choices=Status.choices,
        default=Status.CONTACT_PENDING,
    )
    reason = models.TextField("Lý do", max_length=1000)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_cancellation_requests",
    )
    contact_outcome = models.CharField(
        "Kết quả liên hệ",
        max_length=20,
        choices=ContactOutcome.choices,
        default=ContactOutcome.NOT_REQUIRED,
    )
    contact_attempts = models.PositiveSmallIntegerField("Số lần gọi", default=0)
    contact_notes = models.TextField("Ghi chú cuộc gọi", blank=True, max_length=4000)
    contacted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contacted_order_cancellation_requests",
    )
    manager_resolution_reason = models.TextField("Lý do xử lý", blank=True, max_length=1000)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_order_cancellation_requests",
    )
    requested_at = models.DateTimeField("Thời điểm yêu cầu", auto_now_add=True)
    updated_at = models.DateTimeField("Cập nhật lần cuối", auto_now=True)
    resolved_at = models.DateTimeField("Thời điểm xử lý", null=True, blank=True)

    class Meta:
        ordering = ["-requested_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status__in=["contact_pending", "manager_review"]),
                name="orders_one_open_cancellation_per_order",
            )
        ]
        indexes = [models.Index(fields=["status", "requested_at"])]
        verbose_name = "Yêu cầu hủy đơn"
        verbose_name_plural = "Yêu cầu hủy đơn"

    def __str__(self):
        return f"{self.order.order_number} · {self.get_status_display()}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_sku = models.CharField("Mã sản phẩm", max_length=32)
    product_name = models.CharField("Tên sản phẩm", max_length=120)
    product_category = models.CharField("Danh mục sản phẩm", max_length=16, blank=True)
    shipping_weight_grams = models.PositiveIntegerField("Khối lượng giao hàng (g)", default=0)
    inventory_deducted = models.BooleanField("Đã trừ kho", default=False, editable=False)
    unit_price = models.DecimalField(
        "Đơn giá", max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    quantity = models.PositiveSmallIntegerField("Số lượng", validators=[MinValueValidator(1)])
    line_total = models.DecimalField(
        "Thành tiền", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = "Món trong đơn"
        verbose_name_plural = "Món trong đơn"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"


class OrderCareRequest(models.Model):
    class RequestType(models.TextChoices):
        COMPLAINT = "complaint", "Khiếu nại"
        RETURN = "return", "Yêu cầu đổi/trả hàng"

    class Status(models.TextChoices):
        PENDING = "pending", "Chờ Quản lý xử lý"
        APPROVED = "approved", "Đã chấp thuận"
        REJECTED = "rejected", "Đã từ chối"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="care_requests",
    )
    request_type = models.CharField(max_length=12, choices=RequestType.choices)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    details = models.TextField("Nội dung yêu cầu", max_length=1000)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_care_requests",
    )
    requested_at = models.DateTimeField("Thời điểm gửi", auto_now_add=True)
    resolution_note = models.TextField("Ghi chú xử lý", blank=True, max_length=1000)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_order_care_requests",
    )
    resolved_at = models.DateTimeField("Thời điểm xử lý", null=True, blank=True)

    class Meta:
        ordering = ["-requested_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "request_type"],
                condition=Q(status="pending"),
                name="orders_one_open_care_request_per_type",
            )
        ]
        indexes = [models.Index(fields=["status", "requested_at"])]
        verbose_name = "Yêu cầu khiếu nại / đổi trả"
        verbose_name_plural = "Yêu cầu khiếu nại / đổi trả"

    def __str__(self):
        return f"{self.order.order_number} · {self.get_request_type_display()}"


class OrderPiiAccessLog(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="pii_access_logs",
    )
    accessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_pii_accesses",
    )
    reason = models.CharField(max_length=500)
    accessed_at = models.DateTimeField("Thời điểm truy cập", auto_now_add=True)

    class Meta:
        ordering = ["-accessed_at", "-pk"]
        indexes = [models.Index(fields=["order", "accessed_at"])]
        verbose_name = "Nhật ký truy cập dữ liệu đơn hàng"
        verbose_name_plural = "Nhật ký truy cập dữ liệu đơn hàng"

    def __str__(self):
        return f"{self.order.order_number} · {self.accessed_at:%Y-%m-%d %H:%M}"
