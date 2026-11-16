from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
from urllib.parse import parse_qs, urlencode, urlsplit

from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order

from .gateway import create_vnpay_payment, expire_pending_payments, verify_vnpay_signature
from .models import PaymentTransaction


class VnpayGatewayTests(TestCase):
    def create_order(self):
        return Order.objects.create(
            customer_name="Nguyễn Văn A",
            customer_email="customer@example.com",
            customer_phone="0901234567",
            address="12 Đường X",
            district="Phường Bến Thành",
            city="TP Hồ Chí Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            payment_method=Order.PaymentMethod.VNPAY,
            subtotal=Decimal("100000.00"),
            shipping_fee=Decimal("20000.00"),
            total=Decimal("120000.00"),
        )

    @override_settings(
        VNPAY_ENABLED=True,
        VNPAY_TMN_CODE="TEST123",
        VNPAY_HASH_SECRET="test-secret",
        VNPAY_PAYMENT_URL="https://sandbox.example/pay",
    )
    def test_payment_url_is_signed_and_amount_is_in_vnd_subunits(self):
        order = self.create_order()

        payment, url = create_vnpay_payment(order, RequestFactory().get("/checkout/"))

        params = {
            key: values[0]
            for key, values in parse_qs(urlsplit(url).query).items()
        }
        self.assertEqual(payment.amount, order.total)
        self.assertEqual(params["vnp_Amount"], "12000000")
        self.assertEqual(params["vnp_TmnCode"], "TEST123")
        self.assertTrue(verify_vnpay_signature(params))
        self.assertLessEqual(payment.expires_at, timezone.now() + timedelta(minutes=15))

    @override_settings(VNPAY_HASH_SECRET="test-secret")
    def test_ipn_marks_paid_once_and_rejects_tampered_amount(self):
        order = self.create_order()
        payment = PaymentTransaction.objects.create(
            order=order,
            transaction_ref="payment-reference-1",
            amount=order.total,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        params = {
            "vnp_TxnRef": payment.transaction_ref,
            "vnp_Amount": "12000000",
            "vnp_ResponseCode": "00",
            "vnp_TransactionStatus": "00",
            "vnp_TransactionNo": "gateway-transaction-1",
        }
        signed_query = urlencode(sorted(params.items()))
        params["vnp_SecureHash"] = hmac.new(
            b"test-secret",
            signed_query.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()

        invalid = Client().get(
            reverse("payments:vnpay_ipn"),
            {**params, "vnp_Amount": "1"},
        )
        self.assertEqual(invalid.json()["RspCode"], "97")
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PENDING)

        response = Client().get(reverse("payments:vnpay_ipn"), params)
        self.assertEqual(response.json()["RspCode"], "00")
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PAID)
        self.assertEqual(payment.gateway_transaction_no, "gateway-transaction-1")

        duplicate = Client().get(reverse("payments:vnpay_ipn"), params)
        self.assertEqual(duplicate.json()["RspCode"], "00")
        self.assertEqual(PaymentTransaction.objects.filter(status=PaymentTransaction.Status.PAID).count(), 1)

    def test_expired_payment_cancels_order_and_redacts_customer_details(self):
        order = self.create_order()
        payment = PaymentTransaction.objects.create(
            order=order,
            transaction_ref="payment-reference-2",
            amount=order.total,
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        expired_count = expire_pending_payments()

        self.assertEqual(expired_count, 1)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.EXPIRED)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(order.refund_status, Order.RefundStatus.NOT_REQUIRED)
        self.assertTrue(order.customer_info_redacted)
        self.assertEqual(order.customer_email, "")
