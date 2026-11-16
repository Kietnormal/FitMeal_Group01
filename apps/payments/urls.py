from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("vnpay/return/", views.vnpay_return, name="vnpay_return"),
    path("vnpay/ipn/", views.vnpay_ipn, name="vnpay_ipn"),
]
