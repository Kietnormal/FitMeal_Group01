from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("vnpay/return/", views.vnpay_return, name="vnpay_return"),
    path("vnpay/ipn/", views.vnpay_ipn, name="vnpay_ipn"),
    path("bank/sepay-webhook/", views.sepay_webhook, name="sepay_webhook"),
    path(
        "bank/transfer/<str:transaction_ref>/",
        views.bank_transfer_instructions,
        name="bank_transfer_instructions",
    ),
    path(
        "bank/status/<str:transaction_ref>/",
        views.payment_status,
        name="payment_status",
    ),
]