import hashlib
import hmac
import uuid
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order

from .models import PaymentTransaction

PAYMENT_TIMEOUT = timedelta(minutes=15)


def _signature(params):
    query = urlencode(sorted(params.items()))
    return hmac.new(
        settings.VNPAY_HASH_SECRET.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()


def verify_vnpay_signature(params):
    received = params.get("vnp_SecureHash", "")
    if not received or not settings.VNPAY_HASH_SECRET:
        return False
    signed_params = {
        key: value
        for key, value in params.items()
        if key not in {"vnp_SecureHash", "vnp_SecureHashType"}
    }
    return hmac.compare_digest(_signature(signed_params), received.lower())


def create_vnpay_payment(order, request):
    if not settings.VNPAY_ENABLED:
        raise ImproperlyConfigured("VNPay chưa được cấu hình.")

    now = timezone.localtime()
    expires_at = now + PAYMENT_TIMEOUT
    payment = PaymentTransaction.objects.create(
        order=order,
        transaction_ref=uuid.uuid4().hex,
        amount=order.total,
        expires_at=expires_at,
    )
    return_url = request.build_absolute_uri(reverse("payments:vnpay_return"))
    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": settings.VNPAY_TMN_CODE,
        "vnp_Amount": str(int((Decimal(order.total) * 100).quantize(Decimal("1")))),
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": payment.transaction_ref,
        "vnp_OrderInfo": f"Thanh toan don hang {order.order_number}",
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": return_url,
        "vnp_IpAddr": request.META.get("REMOTE_ADDR", ""),
        "vnp_CreateDate": now.strftime("%Y%m%d%H%M%S"),
        "vnp_ExpireDate": expires_at.strftime("%Y%m%d%H%M%S"),
    }
    signature = _signature(params)
    params["vnp_SecureHashType"] = "HmacSHA512"
    query = urlencode(sorted(params.items()))
    return payment, f"{settings.VNPAY_PAYMENT_URL}?{query}&vnp_SecureHash={signature}"


def expire_pending_payments(*, now=None, batch_size=100):
    now = now or timezone.now()
    payment_ids = list(
        PaymentTransaction.objects.filter(
            status=PaymentTransaction.Status.PENDING,
            expires_at__lte=now,
        )
        .order_by("expires_at", "pk")
        .values_list("pk", flat=True)[:batch_size]
    )
    expired = 0
    for payment_id in payment_ids:
        with transaction.atomic():
            payment = (
                PaymentTransaction.objects.select_for_update()
                .select_related("order")
                .filter(
                    pk=payment_id,
                    status=PaymentTransaction.Status.PENDING,
                    expires_at__lte=now,
                )
                .first()
            )
            if payment is None:
                continue
            payment.status = PaymentTransaction.Status.EXPIRED
            payment.response_code = "EXPIRED"
            payment.save(update_fields=["status", "response_code", "updated_at"])
            order = payment.order
            if order.status == Order.Status.PENDING:
                order.status = Order.Status.CANCELLED
                order.cancelled_at = now
                order.cancellation_reason = "Tự động hủy do chưa thanh toán VNPay trong 15 phút."
                order.refund_status = Order.RefundStatus.NOT_REQUIRED
                order.save(
                    update_fields=[
                        "status",
                        "cancelled_at",
                        "cancellation_reason",
                        "refund_status",
                        "updated_at",
                    ]
                )
            expired += 1
    return expired
