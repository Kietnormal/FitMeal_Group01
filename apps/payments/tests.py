from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import patch

from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.products.models import Product

from .gateway import (
    PaymentGatewayError,
    create_bank_transfer_payment,
    create_momo_payment,
    create_vnpay_payment,
    expire_pending_payments,
    momo_payment_session_key,
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


class NewPaymentMethodTests(TestCase):
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
        MOMO_ENABLED=True,
        MOMO_PARTNER_CODE="MOMO123",
        MOMO_ACCESS_KEY="momo-access",
        MOMO_SECRET_KEY="momo-secret",
        MOMO_CREATE_PAYMENT_URL="https://sandbox.example/momo",
    )
    @patch("apps.payments.gateway.urlopen")
    def test_momo_payment_request_is_signed_and_returns_pay_url(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {"resultCode": 0, "payUrl": "https://sandbox.example/pay"}
        ).encode()
        order = self.create_order(Order.PaymentMethod.MOMO)

        payment, payment_url = create_momo_payment(
            order,
            RequestFactory().get("/checkout/"),
        )

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode())
        raw_signature = "&".join(
            f"{key}={value}"
            for key, value in [
                ("accessKey", "momo-access"),
                ("amount", payload["amount"]),
                ("extraData", payload["extraData"]),
                ("ipnUrl", payload["ipnUrl"]),
                ("orderId", payload["orderId"]),
                ("orderInfo", payload["orderInfo"]),
                ("partnerCode", payload["partnerCode"]),
                ("redirectUrl", payload["redirectUrl"]),
                ("requestId", payload["requestId"]),
                ("requestType", payload["requestType"]),
            ]
        )
        expected_signature = hmac.new(
            b"momo-secret",
            raw_signature.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(payment.provider, PaymentTransaction.Provider.MOMO)
        self.assertEqual(payment.amount, order.total)
        self.assertEqual(payment_url, "https://sandbox.example/pay")
        self.assertEqual(payload["requestType"], "payWithATM")
        self.assertEqual(payload["signature"], expected_signature)

    @override_settings(
        MOMO_PARTNER_CODE="MOMO123",
        MOMO_ACCESS_KEY="momo-access",
        MOMO_SECRET_KEY="momo-secret",
    )
    def test_momo_ipn_verifies_signature_amount_and_marks_payment_paid(self):
        order = self.create_order(Order.PaymentMethod.MOMO)
        payment = PaymentTransaction.objects.create(
            order=order,
            provider=PaymentTransaction.Provider.MOMO,
            transaction_ref="momo-reference-1",
            amount=order.total,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        params = {
            "partnerCode": "MOMO123",
            "requestId": payment.transaction_ref,
            "orderId": payment.transaction_ref,
            "amount": str(int(payment.amount)),
            "orderInfo": "Thanh toan don hang",
            "orderType": "momo_wallet",
            "transId": "momo-transaction-1",
            "message": "Successful.",
            "payType": "qr",
            "responseTime": "20261117120000",
            "resultCode": "0",
            "extraData": "",
        }
        signed_values = {
            "accessKey": "momo-access",
            **params,
        }
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
            f"{key}={signed_values.get(key, '')}" for key in signed_fields
        )
        params["signature"] = hmac.new(
            b"momo-secret",
            raw_signature.encode(),
            hashlib.sha256,
        ).hexdigest()

        client = Client()
        invalid = client.post(
            reverse("payments:momo_ipn"),
            data=json.dumps({**params, "amount": "1"}),
            content_type="application/json",
        )
        self.assertEqual(invalid.json()["resultCode"], 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PENDING)
        pending_return = client.get(reverse("payments:momo_return"), data=params)
        self.assertContains(pending_return, "data-momo-payment-status")
        self.assertContains(pending_return, "Đang xác nhận thanh toán.")

        response = client.post(
            reverse("payments:momo_ipn"),
            data=json.dumps(params),
            content_type="application/json",
        )
        self.assertEqual(response.json()["resultCode"], 0)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PAID)
        self.assertEqual(
            payment.gateway_transaction_no,
            "momo-transaction-1",
        )
        status_response = client.get(
            reverse("payments:momo_payment_status", args=[payment.transaction_ref])
        )
        self.assertTrue(status_response.json()["paid"])
        return_response = client.get(reverse("payments:momo_return"), data=params)
        self.assertContains(return_response, 'class="checkout-success-icon"')
        self.assertContains(return_response, "Thanh toán thành công.")

    @override_settings(
        MOMO_ENABLED=True,
        MOMO_PARTNER_CODE="MOMO123",
        MOMO_ACCESS_KEY="momo-access",
        MOMO_SECRET_KEY="momo-secret",
        MOMO_CREATE_PAYMENT_URL="https://sandbox.example/momo",
    )
    @patch("apps.payments.gateway.urlopen")
    def test_momo_payment_url_must_use_gateway_host(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {"resultCode": 0, "payUrl": "https://unexpected.example/pay"}
        ).encode()

        with self.assertRaises(PaymentGatewayError):
            create_momo_payment(
                self.create_order(Order.PaymentMethod.MOMO),
                RequestFactory().get("/checkout/"),
            )

    @override_settings(
        MOMO_ENABLED=True,
        MOMO_PARTNER_CODE="MOMO123",
        MOMO_ACCESS_KEY="momo-access",
        MOMO_SECRET_KEY="momo-secret",
        MOMO_CREATE_PAYMENT_URL="https://sandbox.example/momo",
    )
    @patch("apps.payments.gateway.urlopen")
    def test_momo_order_shows_local_qr_and_status_endpoint_tracks_ipn(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {"resultCode": 0, "payUrl": "https://sandbox.example/pay?token=sample"}
        ).encode()
        order = self.create_order(Order.PaymentMethod.MOMO)
        payment, gateway_url = create_momo_payment(
            order,
            RequestFactory().get("/checkout/"),
        )
        client = Client()
        session = client.session
        session[momo_payment_session_key(payment.transaction_ref)] = gateway_url
        session.save()

        instructions = client.get(
            reverse(
                "payments:momo_payment_instructions",
                args=[payment.transaction_ref],
            )
        )

        self.assertEqual(instructions.status_code, 200)
        self.assertEqual(instructions["Cache-Control"], "no-store")
        self.assertContains(instructions, "data:image/svg+xml;base64,")
        self.assertContains(instructions, "Quét mã bằng camera điện thoại")
        pending_status = client.get(
            reverse("payments:momo_payment_status", args=[payment.transaction_ref])
        )
        self.assertEqual(pending_status.json()["status"], PaymentTransaction.Status.PENDING)

        payment.status = PaymentTransaction.Status.PAID
        payment.save(update_fields=["status"])
        paid_status = client.get(
            reverse("payments:momo_payment_status", args=[payment.transaction_ref])
        )
        self.assertTrue(paid_status.json()["paid"])

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
