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
        MOMO_PUBLIC_BASE_URL="https://fitmeal-demo.example",
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
        self.assertEqual(
            payload["redirectUrl"],
            "https://fitmeal-demo.example/payments/momo/return/",
        )
        self.assertEqual(
            payload["ipnUrl"],
            "https://fitmeal-demo.example/payments/momo/ipn/",
        )
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
        invalid_signature = client.post(
            reverse("payments:momo_ipn"),
            data=json.dumps({**params, "signature": "invalid-signature"}),
            content_type="application/json",
        )
        self.assertEqual(invalid_signature.json()["resultCode"], 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PENDING)

        invalid = client.post(
            reverse("payments:momo_ipn"),
            data=json.dumps({**params, "amount": "1"}),
            content_type="application/json",
        )
        self.assertEqual(invalid.json()["resultCode"], 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PENDING)
        invalid_return = client.get(
            reverse("payments:momo_return"),
            {**params, "amount": "1"},
        )
        self.assertContains(invalid_return, "Đang chờ xác nhận thanh toán.")
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PENDING)

        return_response = client.get(reverse("payments:momo_return"), data=params)
        self.assertContains(return_response, 'class="checkout-success-icon"')
        self.assertContains(return_response, "Thanh toán thành công.")
        self.assertContains(
            return_response,
            f'href="{reverse("core:tracking")}?token={order.tracking_token}"',
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PAID)

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
        duplicate_ipn = client.post(
            reverse("payments:momo_ipn"),
            data=json.dumps(params),
            content_type="application/json",
        )
        self.assertEqual(duplicate_ipn.json()["resultCode"], 0)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.PAID)
        self.assertEqual(
            PaymentTransaction.objects.filter(
                status=PaymentTransaction.Status.PAID
            ).count(),
            1,
        )
        status_response = client.get(
            reverse("payments:momo_payment_status", args=[payment.transaction_ref])
        )
        self.assertTrue(status_response.json()["paid"])

    @override_settings(
        MOMO_ENABLED=True,
        MOMO_PARTNER_CODE="MOMO123",
        MOMO_ACCESS_KEY="momo-access",
        MOMO_SECRET_KEY="momo-secret",
        MOMO_CREATE_PAYMENT_URL="https://sandbox.example/momo",
        MOMO_PUBLIC_BASE_URL="https://fitmeal-demo.example",
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
        MOMO_PUBLIC_BASE_URL="",
    )
    @patch("apps.payments.gateway.urlopen")
    def test_momo_refuses_localhost_callbacks_before_creating_payment(self, urlopen):
        order = self.create_order(Order.PaymentMethod.MOMO)

        with self.assertRaises(PaymentGatewayError):
            create_momo_payment(order, RequestFactory().get("/checkout/"))

        self.assertFalse(PaymentTransaction.objects.filter(order=order).exists())
        urlopen.assert_not_called()

    @override_settings(
        MOMO_ENABLED=True,
        MOMO_PARTNER_CODE="MOMO123",
        MOMO_ACCESS_KEY="momo-access",
        MOMO_SECRET_KEY="momo-secret",
        MOMO_CREATE_PAYMENT_URL="https://sandbox.example/momo",
        MOMO_PUBLIC_BASE_URL="https://fitmeal-demo.example",
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
        self.assertContains(instructions, "Quét mã để thanh toán")
        self.assertNotContains(instructions, "Mở MoMo trên máy này")
        self.assertContains(
            instructions,
            f'href="{reverse("core:tracking")}?token={order.tracking_token}"',
        )
        self.assertContains(instructions, "Đơn hàng của bạn")
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

    def test_authenticated_momo_payment_page_links_to_customer_order_history(self):
        user = get_user_model().objects.create_user(
            username="momo-customer",
            email="momo-customer@example.com",
            password="strong-test-password",
        )
        order = self.create_order(Order.PaymentMethod.MOMO)
        order.customer = user
        order.save(update_fields=["customer"])
        payment = PaymentTransaction.objects.create(
            order=order,
            provider=PaymentTransaction.Provider.MOMO,
            transaction_ref="momo-customer-reference",
            amount=order.total,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse(
                "payments:momo_payment_instructions",
                args=[payment.transaction_ref],
            )
        )

        self.assertContains(
            response,
            f'href="{reverse("core:account")}?tab=orders#orders"',
        )
        self.assertContains(response, "Đơn hàng của bạn")

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

    def test_instructions_show_waiting_spinner_then_success_panel(self):
        payment = self.create_payment()
        url = reverse("payments:bank_transfer_instructions", args=[payment.transaction_ref])

        pending = Client().get(url)
        self.assertContains(pending, 'class="payment-spinner"')
        self.assertContains(pending, "data-payment-success hidden")
        self.assertContains(pending, f'href="{reverse("core:tracking")}?token={payment.order.tracking_token}"')

        payment.status = PaymentTransaction.Status.PAID
        payment.save(update_fields=["status"])
        paid = Client().get(url)
        self.assertContains(paid, "Thanh toán thành công!")
        self.assertContains(paid, 'class="payment-success-mark"')
        self.assertNotContains(paid, "data-payment-success hidden")
        self.assertNotContains(paid, 'class="payment-spinner"')
