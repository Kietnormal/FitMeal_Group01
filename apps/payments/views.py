import base64
import json
import re
from io import BytesIO
from decimal import Decimal, InvalidOperation

import qrcode
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from qrcode.image.svg import SvgPathImage

from apps.orders.inventory import restore_order_inventory
from apps.orders.models import Order

from .completion import order_complete_context
from .gateway import (
    bank_display_name,
    bank_transfer_content,
    bank_transfer_qr_url,
    expire_pending_payments,
    verify_vnpay_signature,
)
from .models import PaymentTransaction


def _valid_payment_match(payment, params):
    return (
        params.get("vnp_TxnRef") == payment.transaction_ref
        and params.get("vnp_Amount") == str(int(payment.amount * 100))
    )


def _order_followup_url(request, order):
    if request.user.is_authenticated and order.customer_id == request.user.pk:
        return f"{reverse('core:account')}?tab=orders#orders"
    return f"{reverse('core:tracking')}?token={order.tracking_token}"


def _render_order_complete(request, payment):
    return render(
        request,
        "payments/order_complete.html",
        order_complete_context(
            request,
            payment,
            order_url=_order_followup_url(request, payment.order),
        ),
    )


@require_GET
def vnpay_return(request):
    expire_pending_payments()
    params = request.GET.dict()
    valid_signature = verify_vnpay_signature(params)
    payment = None
    if valid_signature:
        payment = (
            PaymentTransaction.objects.select_related("order")
            .filter(
                transaction_ref=params.get("vnp_TxnRef", ""),
                provider=PaymentTransaction.Provider.VNPAY,
            )
            .first()
        )
        if payment and not _valid_payment_match(payment, params):
            payment = None
    return render(
        request,
        "payments/vnpay_result.html",
        {
            "payment": payment,
            "signature_valid": valid_signature,
            "gateway_succeeded": params.get("vnp_ResponseCode") == "00"
            and params.get("vnp_TransactionStatus") == "00",
        },
    )


@csrf_exempt
@require_GET
def vnpay_ipn(request):
    expire_pending_payments()
    params = request.GET.dict()
    if not verify_vnpay_signature(params):
        return JsonResponse({"RspCode": "97", "Message": "Invalid signature"})

    with transaction.atomic():
        payment = (
            PaymentTransaction.objects.select_for_update()
            .select_related("order")
            .filter(
                transaction_ref=params.get("vnp_TxnRef", ""),
                provider=PaymentTransaction.Provider.VNPAY,
            )
            .first()
        )
        if payment is None or not _valid_payment_match(payment, params):
            return JsonResponse({"RspCode": "01", "Message": "Order not found"})
        if payment.status == PaymentTransaction.Status.PAID:
            return JsonResponse({"RspCode": "00", "Message": "Confirm Success"})
        if payment.status != PaymentTransaction.Status.PENDING:
            return JsonResponse({"RspCode": "02", "Message": "Payment already processed"})
        if payment.expires_at <= timezone.now():
            return JsonResponse({"RspCode": "02", "Message": "Payment expired"})

        payment.response_code = params.get("vnp_ResponseCode", "")[:10]
        payment.gateway_transaction_no = params.get("vnp_TransactionNo", "")[:64]
        if (
            payment.response_code == "00"
            and params.get("vnp_TransactionStatus") == "00"
        ):
            payment.status = PaymentTransaction.Status.PAID
            payment.paid_at = timezone.now()
        else:
            payment.status = PaymentTransaction.Status.FAILED
        payment.save(
            update_fields=[
                "status",
                "response_code",
                "gateway_transaction_no",
                "paid_at",
                "updated_at",
            ]
        )
    return JsonResponse({"RspCode": "00", "Message": "Confirm Success"})


@csrf_exempt
@require_POST
def sepay_webhook(request):
    if not verify_sepay_api_key(request):
        return JsonResponse({"success": False}, status=401)
    try:
        event = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    if not isinstance(event, dict):
        return JsonResponse({"success": False, "error": "Invalid payload"}, status=400)
    if str(event.get("transferType", "")).lower() != "in":
        return JsonResponse({"success": True})

    account_number = str(event.get("accountNumber", "")).strip()
    expected_account = str(settings.BANK_TRANSFER_ACCOUNT_NUMBER).strip()
    if account_number != expected_account:
        return JsonResponse({"success": False, "error": "Account mismatch"}, status=400)
    try:
        transfer_amount = Decimal(str(event.get("transferAmount", "")))
    except InvalidOperation:
        return JsonResponse({"success": False, "error": "Invalid amount"}, status=400)
    gateway_transaction_no = str(event.get("id", "")).strip()
    if not gateway_transaction_no:
        return JsonResponse({"success": False, "error": "Missing transaction id"}, status=400)

    code = str(event.get("code") or "").upper()
    content = str(event.get("content") or "").upper()
    transfer_codes = re.findall(r"FM[A-F0-9]{10}", f"{code} {content}")
    if not transfer_codes:
        return JsonResponse({"success": True})

    with transaction.atomic():
        payment = (
            PaymentTransaction.objects.select_for_update()
            .select_related("order")
            .filter(
                provider=PaymentTransaction.Provider.BANK_TRANSFER,
                bank_transfer_code__in=transfer_codes,
            )
            .first()
        )
        if payment is None:
            return JsonResponse(
                {"success": False, "error": "Payment reference not found"},
                status=404,
            )
        if transfer_amount != payment.amount:
            return JsonResponse({"success": False, "error": "Amount mismatch"}, status=400)
        if payment.status == PaymentTransaction.Status.PAID:
            return JsonResponse({"success": True})
        if (
            payment.status != PaymentTransaction.Status.PENDING
            or payment.expires_at <= timezone.now()
            or payment.order.status == Order.Status.CANCELLED
        ):
            return JsonResponse({"success": False, "error": "Payment expired"}, status=400)
        if PaymentTransaction.objects.filter(
            gateway_transaction_no=gateway_transaction_no,
            status=PaymentTransaction.Status.PAID,
        ).exists():
            return JsonResponse({"success": False, "error": "Duplicate transaction"}, status=409)

        payment.status = PaymentTransaction.Status.PAID
        payment.paid_at = timezone.now()
        payment.response_code = "00"
        payment.gateway_transaction_no = gateway_transaction_no[:64]
        payment.save(
            update_fields=[
                "status",
                "paid_at",
                "response_code",
                "gateway_transaction_no",
                "updated_at",
            ]
        )
    return JsonResponse({"success": True})


@require_GET
def bank_transfer_instructions(request, transaction_ref):
    expire_pending_payments()
    payment = get_object_or_404(
        PaymentTransaction.objects.select_related("order"),
        transaction_ref=transaction_ref,
        provider=PaymentTransaction.Provider.BANK_TRANSFER,
    )
    if payment.status == PaymentTransaction.Status.PAID:
        return _render_order_complete(request, payment)
    return render(
        request,
        "payments/bank_transfer_instructions.html",
        {
            "payment": payment,
            "bank_qr_url": bank_transfer_qr_url(payment),
            "bank_code": settings.BANK_TRANSFER_BANK_CODE,
            "bank_name": bank_display_name(),
            "transfer_content": bank_transfer_content(payment),
            "order_url": _order_followup_url(request, payment.order),
            "account_number": settings.BANK_TRANSFER_ACCOUNT_NUMBER,
            "account_name": settings.BANK_TRANSFER_ACCOUNT_NAME,
            "payment_status_url": reverse(
                "payments:payment_status",
                args=[payment.transaction_ref],
            ),
        },
    )


@require_GET
def payment_status(request, transaction_ref):
    expire_pending_payments()
    payment = get_object_or_404(
        PaymentTransaction,
        transaction_ref=transaction_ref,
        provider=PaymentTransaction.Provider.BANK_TRANSFER,
    )
    return JsonResponse(
        {
            "status": payment.status,
            "status_display": payment.get_status_display(),
            "paid": payment.status == PaymentTransaction.Status.PAID,
        }
    )


def verify_sepay_api_key(request):
    authorization = request.headers.get("Authorization", "")
    expected = f"Apikey {settings.SEPAY_API_KEY}"
    return bool(settings.SEPAY_API_KEY) and constant_time_compare(
        authorization, expected
    )