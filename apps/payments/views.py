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

from .gateway import (
    bank_display_name,
    bank_transfer_content,
    bank_transfer_qr_url,
    expire_pending_payments,
    momo_payment_session_key,
    verify_momo_signature,
    verify_sepay_api_key,
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


def _momo_callback_result(code, message):
    return JsonResponse({"resultCode": code, "message": message})


@csrf_exempt
@require_POST
def momo_ipn(request):
    if not request.content_type.startswith("application/json"):
        return _momo_callback_result(1, "Invalid content type")
    try:
        params = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _momo_callback_result(1, "Invalid JSON")
    if not isinstance(params, dict) or not verify_momo_signature(params):
        return _momo_callback_result(1, "Invalid signature")
    if params.get("partnerCode") != settings.MOMO_PARTNER_CODE:
        return _momo_callback_result(1, "Invalid partner")

    with transaction.atomic():
        payment = (
            PaymentTransaction.objects.select_for_update()
            .select_related("order")
            .filter(
                transaction_ref=params.get("orderId", ""),
                provider=PaymentTransaction.Provider.MOMO,
            )
            .first()
        )
        if payment is None or params.get("requestId") != payment.transaction_ref:
            return _momo_callback_result(1, "Payment not found")
        try:
            callback_amount = Decimal(str(params.get("amount", "")))
        except InvalidOperation:
            return _momo_callback_result(1, "Invalid amount")
        if callback_amount != payment.amount:
            return _momo_callback_result(1, "Amount mismatch")
        if payment.status == PaymentTransaction.Status.PAID:
            return _momo_callback_result(0, "Success")
        if (
            payment.status != PaymentTransaction.Status.PENDING
            or payment.expires_at <= timezone.now()
            or payment.order.status == Order.Status.CANCELLED
        ):
            return _momo_callback_result(1, "Payment is no longer pending")

        payment.response_code = str(params.get("resultCode", ""))[:10]
        payment.gateway_transaction_no = str(params.get("transId", ""))[:64]
        if str(params.get("resultCode")) == "0":
            if PaymentTransaction.objects.filter(
                provider=PaymentTransaction.Provider.MOMO,
                gateway_transaction_no=payment.gateway_transaction_no,
                status=PaymentTransaction.Status.PAID,
            ).exists():
                return _momo_callback_result(1, "Duplicate transaction")
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
        if (
            payment.status == PaymentTransaction.Status.FAILED
            and payment.order.status == Order.Status.PENDING
        ):
            order = payment.order
            order.status = Order.Status.CANCELLED
            order.cancelled_at = timezone.now()
            order.cancellation_reason = "Tự động hủy do giao dịch MoMo thất bại."
            order.cancellation_reason_category = (
                Order.CancellationReasonCategory.PAYMENT_EXPIRED
            )
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
    return _momo_callback_result(0, "Success")


@require_GET
def momo_return(request):
    expire_pending_payments()
    params = request.GET.dict()
    valid_signature = verify_momo_signature(params)
    payment = None
    if valid_signature:
        payment = (
            PaymentTransaction.objects.select_related("order")
            .filter(
                transaction_ref=params.get("orderId", ""),
                provider=PaymentTransaction.Provider.MOMO,
            )
            .first()
        )
        if payment and str(params.get("amount", "")) != str(int(payment.amount)):
            payment = None
        if (
            payment
            and params.get("partnerCode") == settings.MOMO_PARTNER_CODE
            and params.get("requestId") == payment.transaction_ref
            and str(params.get("resultCode")) == "0"
            and params.get("transId")
        ):
            gateway_transaction_no = str(params["transId"])[:64]
            with transaction.atomic():
                payment = (
                    PaymentTransaction.objects.select_for_update()
                    .select_related("order")
                    .get(pk=payment.pk)
                )
                if (
                    payment.status == PaymentTransaction.Status.PENDING
                    and payment.expires_at > timezone.now()
                    and payment.order.status != Order.Status.CANCELLED
                    and not PaymentTransaction.objects.filter(
                        provider=PaymentTransaction.Provider.MOMO,
                        gateway_transaction_no=gateway_transaction_no,
                        status=PaymentTransaction.Status.PAID,
                    )
                    .exclude(pk=payment.pk)
                    .exists()
                ):
                    payment.status = PaymentTransaction.Status.PAID
                    payment.paid_at = timezone.now()
                    payment.response_code = str(params.get("resultCode", ""))[:10]
                    payment.gateway_transaction_no = gateway_transaction_no
                    payment.save(
                        update_fields=[
                            "status",
                            "paid_at",
                            "response_code",
                            "gateway_transaction_no",
                            "updated_at",
                        ]
                    )
    return render(
        request,
        "payments/payment_result.html",
        {
            "payment": payment,
            "signature_valid": valid_signature,
            "gateway_succeeded": str(params.get("resultCode")) == "0",
            "payment_provider": "MoMo",
            "payment_status_url": (
                reverse("payments:momo_payment_status", args=[payment.transaction_ref])
                if payment
                else ""
            ),
            "order_url": (
                _order_followup_url(request, payment.order)
                if payment
                else reverse("core:home")
            ),
        },
    )


def _momo_qr_data_url(payment_url):
    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data(payment_url)
    qr.make(fit=True)
    image = qr.make_image(image_factory=SvgPathImage)
    buffer = BytesIO()
    image.save(buffer)
    return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode(
        "ascii"
    )


@require_GET
def momo_payment_instructions(request, transaction_ref):
    expire_pending_payments()
    payment = get_object_or_404(
        PaymentTransaction.objects.select_related("order"),
        transaction_ref=transaction_ref,
        provider=PaymentTransaction.Provider.MOMO,
    )
    gateway_payment_url = request.session.get(
        momo_payment_session_key(payment.transaction_ref),
        "",
    )
    qr_data_url = (
        _momo_qr_data_url(gateway_payment_url)
        if gateway_payment_url and payment.status == PaymentTransaction.Status.PENDING
        else ""
    )
    response = render(
        request,
        "payments/momo_payment_instructions.html",
        {
            "payment": payment,
            "qr_data_url": qr_data_url,
            "payment_status_url": reverse(
                "payments:momo_payment_status",
                args=[payment.transaction_ref],
            ),
            "order_url": _order_followup_url(request, payment.order),
        },
    )
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def momo_payment_status(request, transaction_ref):
    expire_pending_payments()
    payment = get_object_or_404(
        PaymentTransaction,
        transaction_ref=transaction_ref,
        provider=PaymentTransaction.Provider.MOMO,
    )
    if payment.status != PaymentTransaction.Status.PENDING:
        request.session.pop(momo_payment_session_key(payment.transaction_ref), None)
    response = JsonResponse(
        {
            "status": payment.status,
            "status_display": payment.get_status_display(),
            "paid": payment.status == PaymentTransaction.Status.PAID,
        }
    )
    response["Cache-Control"] = "no-store"
    return response


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
