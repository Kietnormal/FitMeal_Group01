from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .gateway import expire_pending_payments, verify_vnpay_signature
from .models import PaymentTransaction


def _valid_payment_match(payment, params):
    return (
        params.get("vnp_TxnRef") == payment.transaction_ref
        and params.get("vnp_Amount") == str(int(payment.amount * 100))
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
            .filter(transaction_ref=params.get("vnp_TxnRef", ""))
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
            .filter(transaction_ref=params.get("vnp_TxnRef", ""))
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
