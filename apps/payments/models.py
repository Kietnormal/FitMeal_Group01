from django.db import models


class PaymentTransaction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Chờ thanh toán"
        PAID = "paid", "Đã thanh toán"
        FAILED = "failed", "Thanh toán thất bại"
        EXPIRED = "expired", "Hết hạn"

    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payment_transaction",
    )
    transaction_ref = models.CharField(max_length=32, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    gateway_transaction_no = models.CharField(max_length=64, blank=True)
    response_code = models.CharField(max_length=10, blank=True)
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["status", "expires_at"])]
        verbose_name = "Giao dịch thanh toán"
        verbose_name_plural = "Giao dịch thanh toán"

    def __str__(self):
        return f"{self.transaction_ref} · {self.get_status_display()}"
