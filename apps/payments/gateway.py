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


def momo_payment_session_key(transaction_ref):
    return f"momo_payment_url_{transaction_ref}"


def _momo_callback_url(request, route_name):
    public_base_url = settings.MOMO_PUBLIC_BASE_URL.strip().rstrip("/")
    callback_path = reverse(route_name)
    if not public_base_url:
        callback_url = request.build_absolute_uri(callback_path)
        try:
            parsed_url = urlsplit(callback_url)
        except ValueError as error:
            raise PaymentGatewayError(
                "MoMo cần URL callback HTTPS công khai; hãy cấu hình MOMO_PUBLIC_BASE_URL."
            ) from error
    else:
        try:
            parsed_url = urlsplit(public_base_url)
        except ValueError as error:
            raise PaymentGatewayError(
                "MOMO_PUBLIC_BASE_URL phải là hostname HTTPS công khai hợp lệ."
            ) from error

    try:
        port = parsed_url.port
    except ValueError as error:
        raise PaymentGatewayError(
            "MOMO_PUBLIC_BASE_URL phải là hostname HTTPS công khai hợp lệ."
        ) from error
    hostname = (parsed_url.hostname or "").rstrip(".").casefold()
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if (
        parsed_url.scheme != "https"
        or not hostname
        or (address is None and "." not in hostname)
        or hostname == "localhost"
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
        or (address is not None and not address.is_global)
        or parsed_url.username
        or parsed_url.password
        or port not in (None, 443)
        or parsed_url.path not in ("", "/")
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise PaymentGatewayError(
            "MoMo cần URL callback HTTPS công khai; hãy cấu hình MOMO_PUBLIC_BASE_URL."
        )
    return (
        f"{public_base_url}{callback_path}"
        if public_base_url
        else callback_url
    )


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


def create_momo_payment(order, request):
    if not settings.MOMO_ENABLED:
        raise ImproperlyConfigured("MoMo chưa được cấu hình.")

    redirect_url = _momo_callback_url(request, "payments:momo_return")
    ipn_url = _momo_callback_url(request, "payments:momo_ipn")
    now = timezone.localtime()
    payment = PaymentTransaction.objects.create(
        order=order,
        provider=PaymentTransaction.Provider.MOMO,
        transaction_ref=uuid.uuid4().hex,
        amount=order.total,
        expires_at=now + PAYMENT_TIMEOUT,
    )
    params = {
        "partnerCode": settings.MOMO_PARTNER_CODE,
        "requestId": payment.transaction_ref,
        "amount": str(int(payment.amount)),
        "orderId": payment.transaction_ref,
        "orderInfo": f"Thanh toan don hang {order.order_number}",
        "redirectUrl": redirect_url,
        "ipnUrl": ipn_url,
        "requestType": "payWithATM",
        "extraData": "",
        "lang": "vi",
    }
    signed_fields = (
        "accessKey",
        "amount",
        "extraData",
        "ipnUrl",
        "orderId",
        "orderInfo",
        "partnerCode",
        "redirectUrl",
        "requestId",
        "requestType",
    )
    raw_signature = "&".join(
        f"{key}={settings.MOMO_ACCESS_KEY if key == 'accessKey' else params[key]}"
        for key in signed_fields
    )
    params["signature"] = hmac.new(
        settings.MOMO_SECRET_KEY.encode("utf-8"),
        raw_signature.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    http_request = Request(
        settings.MOMO_CREATE_PAYMENT_URL,
        data=json.dumps(params).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(http_request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError, TimeoutError) as error:
        raise PaymentGatewayError("Không thể kết nối cổng thanh toán MoMo.") from error
    if not isinstance(result, dict):
        raise PaymentGatewayError("MoMo trả về phản hồi thanh toán không hợp lệ.")
    returned_url = result.get("payUrl")
    expected_host = urlsplit(settings.MOMO_CREATE_PAYMENT_URL).hostname
    try:
        parsed_returned_url = (
            urlsplit(returned_url) if isinstance(returned_url, str) else None
        )
        returned_port = parsed_returned_url.port if parsed_returned_url else None
    except ValueError:
        parsed_returned_url = None
        returned_port = None
    if (
        str(result.get("resultCode")) != "0"
        or parsed_returned_url is None
        or parsed_returned_url.scheme != "https"
        or parsed_returned_url.hostname != expected_host
        or parsed_returned_url.username
        or parsed_returned_url.password
        or returned_port not in (None, 443)
    ):
        raise PaymentGatewayError(
            "MoMo chưa tạo được liên kết thanh toán hợp lệ. Vui lòng thử lại."
        )
    return payment, returned_url


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


def verify_momo_signature(params):
    received = params.get("signature", "")
    if not received or not settings.MOMO_SECRET_KEY or not settings.MOMO_ACCESS_KEY:
        return False
    signed_fields = (
        "accessKey",
        "amount",
        "extraData",
        "message",
        "orderId",
        "orderInfo",
        "orderType",
        "partnerCode",
        "payType",
        "requestId",
        "responseTime",
        "resultCode",
        "transId",
    )
    raw_signature = "&".join(
        f"{key}={settings.MOMO_ACCESS_KEY if key == 'accessKey' else params.get(key, '')}"
        for key in signed_fields
    )
    expected = hmac.new(
        settings.MOMO_SECRET_KEY.encode("utf-8"),
        raw_signature.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received.lower())


def verify_sepay_api_key(request):
    authorization = request.headers.get("Authorization", "")
    expected = f"Apikey {settings.SEPAY_API_KEY}"
    return bool(settings.SEPAY_API_KEY) and constant_time_compare(
        authorization, expected
    )


def bank_transfer_qr_url(payment):
    bank = quote(settings.BANK_TRANSFER_BANK_CODE, safe="")
    account = quote(settings.BANK_TRANSFER_ACCOUNT_NUMBER, safe="")
    params = urlencode(
        {
            "amount": str(int(payment.amount)),
            "addInfo": payment.bank_transfer_code,
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
