import hashlib
import hmac
import ipaddress
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from apps.orders.models import Order
from apps.orders.inventory import restore_order_inventory

from .models import PaymentTransaction


PAYMENT_TIMEOUT = timedelta(minutes=15)
BANK_TRANSFER_TIMEOUT = timedelta(hours=24)


class PaymentGatewayError(Exception):
    pass


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


def create_bank_transfer_payment(order, request):
    if not settings.BANK_TRANSFER_ENABLED:
        raise ImproperlyConfigured("Chuyển khoản ngân hàng chưa được cấu hình.")

    transfer_code = f"FM{uuid.uuid4().hex[:10].upper()}"
    payment = PaymentTransaction.objects.create(
        order=order,
        provider=PaymentTransaction.Provider.BANK_TRANSFER,
        transaction_ref=uuid.uuid4().hex,
        bank_transfer_code=transfer_code,
        amount=order.total,
        expires_at=timezone.now() + BANK_TRANSFER_TIMEOUT,
    )
    return payment, request.build_absolute_uri(
        reverse("payments:bank_transfer_instructions", args=[payment.transaction_ref])
    )


def bank_display_name(bank_code=None):
    code = (bank_code if bank_code is not None else settings.BANK_TRANSFER_BANK_CODE).strip()
    return BANK_DISPLAY_NAMES.get(code.upper(), code)


def verify_sepay_api_key(request):
    authorization = request.headers.get("Authorization", "")
    expected = f"Apikey {settings.SEPAY_API_KEY}"
    return bool(settings.SEPAY_API_KEY) and constant_time_compare(
        authorization, expected
    )


BANK_DISPLAY_NAMES = {
    "ACB": "ACB",
    "BIDV": "BIDV",
    "ICB": "VietinBank",
    "MB": "MB Bank",
    "STB": "Sacombank",
    "TCB": "Techcombank",
    "TPB": "TPBank",
    "VBA": "Agribank",
    "VCB": "Vietcombank",
    "VPB": "VPBank",
}


def bank_transfer_content(payment):
    """Transfer note the customer must use; always contains the order's FM... code."""
    prefix = settings.BANK_TRANSFER_CONTENT_PREFIX.strip()
    return f"{prefix} {payment.bank_transfer_code}" if prefix else payment.bank_transfer_code


def bank_transfer_qr_url(payment):
    bank = quote(settings.BANK_TRANSFER_BANK_CODE, safe="")
    account = quote(settings.BANK_TRANSFER_ACCOUNT_NUMBER, safe="")
    params = urlencode(
        {
            "amount": str(int(payment.amount)),
            "addInfo": bank_transfer_content(payment),
            "accountName": settings.BANK_TRANSFER_ACCOUNT_NAME,
        }
    )
    return f"https://img.vietqr.io/image/{bank}-{account}-compact2.png?{params}"


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
                order.cancellation_reason = "Tự động hủy do chưa thanh toán trong thời hạn quy định."
                order.cancellation_reason_category = Order.CancellationReasonCategory.PAYMENT_EXPIRED
                order.refund_status = Order.RefundStatus.NOT_REQUIRED
                order.save(
                    update_fields=[
                        "status",
                        "cancelled_at",
                        "cancellation_reason",
                        "cancellation_reason_category",
                        "refund_status",
                        "updated_at",
                    ]
                )
                restore_order_inventory(order)
            expired += 1
    return expired