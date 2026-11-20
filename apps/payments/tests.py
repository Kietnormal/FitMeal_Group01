from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.products.models import Product

from .gateway import (
    PaymentGatewayError,
    bank_transfer_qr_url,
    create_bank_transfer_payment,
    create_vnpay_payment,
    expire_pending_payments,
    verify_vnpay_signature,
)
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
        product = Product.objects.create(
            sku="FM-PAYMENT-001",
            slug="payment-whey",
            name="Whey",
            category=Product.Category.DRY_GOODS,
            description="Bột whey",
            price=Decimal("100000.00"),
            stock_quantity=3,
            shipping_weight_grams=500,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_sku=product.sku,
            product_name=product.name,
            product_category=product.category,
            unit_price=product.price,
            quantity=2,
            line_total=product.price * 2,
            inventory_deducted=True,
        )
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
        self.assertEqual(
            order.cancellation_reason_category,
            Order.CancellationReasonCategory.PAYMENT_EXPIRED,
        )
        self.assertTrue(order.customer_info_redacted)
        self.assertEqual(order.customer_email, "")
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 5)
        self.assertFalse(OrderItem.objects.get(order=order).inventory_deducted)




class SepayWebhookTests(TestCase):
    def create_order(self, payment_method):
        return Order.objects.create(
            customer_name="Nguyễn Văn A",
            customer_email="customer@example.com",
            customer_phone="0901234567",
            address="12 Đường X",
            district="Phường Bến Thành",
            city="TP Hồ Chí Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            payment_method=payment_method,
            subtotal=Decimal("100000.00"),
            shipping_fee=Decimal("20000.00"),
            total=Decimal("120000.00"),
        )

    @override_settings(
        BANK_TRANSFER_ENABLED=True,
        BANK_TRANSFER_BANK_CODE="VCB",
        BANK_TRANSFER_ACCOUNT_NUMBER="123456789",
        BANK_TRANSFER_ACCOUNT_NAME="FITMEAL",
        SEPAY_API_KEY="test-sepay-key",
    )
    def test_sepay_webhook_matches_reference_account_and_exact_amount(self):
        order = self.create_order(Order.PaymentMethod.BANK_TRANSFER)
        payment, payment_url = create_bank_transfer_payment(
            order,
            RequestFactory().get("/checkout/"),
        )
        self.assertIn(
            reverse(
                "payments:bank_transfer_instructions",
                args=[payment.transaction_ref],
            ),
            payment_url,
        )
        instructions_response = Client().get(
            reverse(
                "payments:bank_transfer_instructions",
                args=[payment.transaction_ref],
            )
        )
        self.assertEqual(instructions_response.status_code, 200)
        self.assertContains(instructions_response, payment.bank_transfer_code)
        self.assertContains(instructions_response, "Quét mã để thanh toán")
        event = {
            "id": 92704,
            "accountNumber": "123456789",
            "content": f"Thanh toan {payment.bank_transfer_code}",
            "transferType": "in",
            "transferAmount": 120000,
        }
        client = Client()

        unauthorized = client.post(
            reverse("payments:sepay_webhook"),
            data=json.dumps(event),
            content_type="application/json",
        )
        self.assertEqual(unauthorized.status_code, 401)

        invalid = client.post(
            reverse("payments:sepay_webhook"),
            data=json.dumps({**event, "transferAmount": 120001}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Apikey test-sepay-key",
        )
        self.assertEqual(invalid.status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PENDING)

        response = client.post(
            reverse("payments:sepay_webhook"),
            data=json.dumps(event),
            content_type="application/json",
            HTTP_AUTHORIZATION="Apikey test-sepay-key",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PAID)
        self.assertEqual(payment.gateway_transaction_no, "92704")

        duplicate = client.post(
            reverse("payments:sepay_webhook"),
            data=json.dumps(event),
            content_type="application/json",
            HTTP_AUTHORIZATION="Apikey test-sepay-key",
        )
        self.assertTrue(duplicate.json()["success"])
        self.assertEqual(
            PaymentTransaction.objects.filter(status=PaymentTransaction.Status.PAID).count(),
            1,
        )


@override_settings(
    BANK_TRANSFER_ENABLED=True,
    BANK_TRANSFER_BANK_CODE="ICB",
    BANK_TRANSFER_ACCOUNT_NUMBER="102881923455",
    BANK_TRANSFER_ACCOUNT_NAME="FITMEAL DEMO",
    BANK_TRANSFER_CONTENT_PREFIX="SEVQR",
    SEPAY_API_KEY="test-sepay-key",
)
class BankTransferContentPrefixTests(TestCase):
    def create_payment(self):
        order = Order.objects.create(
            customer_name="Khách",
            customer_email="khach@example.com",
            customer_phone="0901234567",
            address="1 Đường A",
            district="Quận 1",
            city="TP Hồ Chí Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            payment_method=Order.PaymentMethod.BANK_TRANSFER,
            subtotal=Decimal("60000.00"),
            shipping_fee=Decimal("0.00"),
            total=Decimal("60000.00"),
        )
        payment, _ = create_bank_transfer_payment(order, RequestFactory().get("/checkout/"))
        return payment

    def test_instructions_and_qr_use_the_bank_keyword_prefix(self):
        payment = self.create_payment()

        response = Client().get(reverse("payments:bank_transfer_instructions", args=[payment.transaction_ref]))

        self.assertContains(response, f"SEVQR {payment.bank_transfer_code}")
        self.assertContains(response, "VietinBank")
        self.assertIn(f"addInfo=SEVQR+{payment.bank_transfer_code}", bank_transfer_qr_url(payment))

    def test_webhook_with_prefixed_content_marks_payment_paid(self):
        for content in ("SEVQR {code}", "SEVQR{code} chuyen tien"):
            with self.subTest(content=content):
                payment = self.create_payment()
                response = Client().post(
                    reverse("payments:sepay_webhook"),
                    data=json.dumps({
                        "id": f"tx-{payment.pk}",
                        "accountNumber": "102881923455",
                        "content": content.format(code=payment.bank_transfer_code),
                        "transferType": "in",
                        "transferAmount": 60000,
                    }),
                    content_type="application/json",
                    HTTP_AUTHORIZATION="Apikey test-sepay-key",
                )
                self.assertEqual(response.status_code, 200)
                payment.refresh_from_db()
                self.assertEqual(payment.status, PaymentTransaction.Status.PAID)

    def test_instructions_show_spinner_then_the_order_complete_page(self):
        payment = self.create_payment()
        OrderItem.objects.create(
            order=payment.order,
            product_sku="FM-TRA",
            product_name="Nước trà",
            product_category=Product.Category.DRINK,
            unit_price=Decimal("60000.00"),
            quantity=1,
            line_total=Decimal("60000.00"),
        )
        url = reverse("payments:bank_transfer_instructions", args=[payment.transaction_ref])

        pending = Client().get(url)
        self.assertContains(pending, 'class="payment-spinner"')
        self.assertNotContains(pending, "data-order-complete")

        payment.status = PaymentTransaction.Status.PAID
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "paid_at"])
        paid = Client().get(url)
        self.assertContains(paid, "data-order-complete")
        self.assertContains(paid, "Thanh toán thành công")
        self.assertContains(paid, 'class="payment-success-mark"')
        self.assertContains(paid, payment.order.order_number)
        self.assertContains(paid, "Nước trà")
        self.assertContains(paid, "Đồ tươi · SL 1")
        for title in ("Đã thanh toán", "Cửa hàng xác nhận", "Đang chuẩn bị", "Đang giao"):
            self.assertContains(paid, title)
        self.assertContains(paid, 'class="is-done"')
        self.assertContains(paid, 'class="is-current" aria-current="step"')
        self.assertContains(paid, f'href="{reverse("core:tracking")}?token={payment.order.tracking_token}"')
        self.assertNotContains(paid, 'class="payment-spinner"')

    def test_order_complete_steps_follow_the_order_status(self):
        payment = self.create_payment()
        payment.status = PaymentTransaction.Status.PAID
        payment.paid_at = timezone.now()
        payment.save(update_fields=["status", "paid_at"])
        payment.order.status = Order.Status.PREPARING
        payment.order.save(update_fields=["status"])

        response = Client().get(reverse("payments:bank_transfer_instructions", args=[payment.transaction_ref]))

        steps = response.context["steps"]
        self.assertEqual([step["state"] for step in steps], ["done", "done", "current", "upcoming"])
