import json
from importlib import import_module
from datetime import datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib import admin
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PointsTransaction, User
from apps.products.forms import ProductCreateForm
from apps.products.models import InventoryRestockRequest, Product, ProductActivity
from apps.payments.models import PaymentTransaction

from .admin import OrderAdmin
from .delivery import finalize_expired_delivery_confirmations
from .models import (
    DeliveryIssue,
    Order,
    OrderCancellationRequest,
    OrderCareRequest,
    OrderItem,
    OrderPiiAccessLog,
)
from .privacy import purge_expired_order_pii


@override_settings(
    BANK_TRANSFER_ENABLED=True,
    BANK_TRANSFER_BANK_CODE="VCB",
    BANK_TRANSFER_ACCOUNT_NUMBER="123456789",
    BANK_TRANSFER_ACCOUNT_NAME="FITMEAL",
    SEPAY_API_KEY="test-sepay-key",
)
class OrderApiTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            sku="FM-ORDER-001",
            slug="order-whey",
            name="Whey",
            category=Product.Category.DRINK,
            description="Thức uống",
            price=Decimal("100000.00"),
        )
        self.payload = {
            "name": "Nguyễn Văn A",
            "email": "customer@example.com",
            "phone": "0901234567",
            "address": "12 Đường X",
            "district": "Quận 1",
            "city": "TP Hồ Chí Minh",
            "delivery_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
            "delivery_slot": Order.DeliverySlot.MORNING,
            "note": "",
            "payment": Order.PaymentMethod.BANK_TRANSFER,
            "accept_policy": True,
            "items": [{"id": self.product.slug, "quantity": 2}],
        }

    def post_order(self, payload=None):
        return self.client.post(
            reverse("orders:create"),
            data=json.dumps(payload if payload is not None else self.payload),
            content_type="application/json",
        )

    def create_dry_product(self, *, slug, stock_quantity):
        return Product.objects.create(
            sku=f"FM-{slug.upper()}",
            slug=slug,
            name="Đồ khô kiểm tra",
            category=Product.Category.DRY_GOODS,
            description="Sản phẩm khô",
            price=Decimal("100000.00"),
            stock_quantity=stock_quantity,
            shipping_weight_grams=500,
        )

    def create_awaiting_confirmation_order(self):
        create_response = self.post_order()
        order = Order.objects.get()
        order.status = Order.Status.AWAITING_CUSTOMER_CONFIRMATION
        order.delivery_confirmation_deadline = timezone.now() + timedelta(minutes=3)
        order.save(update_fields=["status", "delivery_confirmation_deadline"])
        return order, create_response.json()["tracking_token"]

    def test_create_order_calculates_prices_and_persists_item_snapshots(self):
        response = self.post_order()

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        item = OrderItem.objects.get(order=order)
        self.assertEqual(order.delivery_region, Order.DeliveryRegion.HO_CHI_MINH_CITY)
        self.assertEqual(order.subtotal, Decimal("200000.00"))
        self.assertEqual(order.shipping_fee, Decimal("20000.00"))
        self.assertEqual(order.total, Decimal("220000.00"))
        self.assertEqual(item.product_name, "Whey")
        self.assertEqual(item.unit_price, Decimal("100000.00"))
        self.assertEqual(item.quantity, 2)
        self.assertFalse(item.inventory_deducted)
        self.assertIsNone(self.product.stock_quantity)
        self.assertTrue(response.json()["tracking_token"])

    def test_overselling_order_is_accepted_and_staff_restock_alert_is_created(self):
        product = self.create_dry_product(slug="tracked-stock", stock_quantity=14)
        payload = {
            **self.payload,
            "delivery_slot": Order.DeliverySlot.COURIER,
            "items": [{"id": product.slug, "quantity": 14}],
        }

        response = self.post_order(payload)

        self.assertEqual(response.status_code, 201)
        product.refresh_from_db()
        item = OrderItem.objects.get()
        self.assertEqual(product.stock_quantity, 0)
        self.assertTrue(item.inventory_deducted)

        oversell_response = self.post_order(payload)

        self.assertEqual(oversell_response.status_code, 201)
        self.assertNotIn("error", oversell_response.json())
        self.assertNotIn("tồn kho", json.dumps(oversell_response.json()).casefold())
        self.assertEqual(Order.objects.count(), 2)
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 0)
        restock_request = InventoryRestockRequest.objects.get(product=product)
        self.assertEqual(restock_request.status, InventoryRestockRequest.Status.STAFF_ALERT)
        self.assertEqual(restock_request.requested_quantity, 14)
        self.assertEqual(restock_request.available_quantity, 0)

        repeat_response = self.post_order(
            {**payload, "items": [{"id": product.slug, "quantity": 15}]}
        )
        self.assertEqual(repeat_response.status_code, 201)
        restock_request.refresh_from_db()
        self.assertEqual(restock_request.requested_quantity, 29)
        self.assertEqual(restock_request.attempt_count, 2)
        self.assertEqual(
            OrderItem.objects.filter(
                product=product,
                inventory_deducted=False,
            ).count(),
            2,
        )

    def test_shortage_in_multiple_products_creates_staff_alert_for_each(self):
        first_product = self.create_dry_product(slug="first-shortage", stock_quantity=1)
        second_product = self.create_dry_product(slug="second-shortage", stock_quantity=2)
        payload = {
            **self.payload,
            "delivery_slot": Order.DeliverySlot.COURIER,
            "items": [
                {"id": first_product.slug, "quantity": 3},
                {"id": second_product.slug, "quantity": 4},
            ],
        }

        response = self.post_order(payload)

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("error", response.json())
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(
            set(
                InventoryRestockRequest.objects.values_list(
                    "product_id",
                    flat=True,
                )
            ),
            {first_product.pk, second_product.pk},
        )

    @patch("apps.orders.views.send_mail", return_value=1)
    def test_cancelling_order_restores_deducted_stock_once(self, send_mail):
        customer = User.objects.create_user(
            username="inventory-customer",
            email="inventory-customer@example.com",
            password="Customer-Strong-2026!",
        )
        self.client.force_login(customer)
        product = self.create_dry_product(slug="cancel-stock", stock_quantity=8)

        create_response = self.post_order(
            {
                **self.payload,
                "email": customer.email,
                "delivery_slot": Order.DeliverySlot.COURIER,
                "items": [{"id": product.slug, "quantity": 3}],
            }
        )
        self.assertEqual(create_response.status_code, 201)
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 5)
        order = Order.objects.get()

        cancel_url = reverse("orders:customer_cancel", args=[order.pk])
        response = self.client.post(cancel_url, {"reason": "Khách đổi ý"})
        self.assertEqual(response.status_code, 302)

        product.refresh_from_db()
        item = OrderItem.objects.get(order=order)
        self.assertEqual(product.stock_quantity, 8)
        self.assertFalse(item.inventory_deducted)

        self.client.post(cancel_url, {"reason": "Gửi lại yêu cầu"})
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 8)
        send_mail.assert_called_once()

    @patch("apps.orders.views.send_mail", return_value=1)
    def test_cancelling_backordered_order_closes_restock_alert(self, send_mail):
        customer = User.objects.create_user(
            username="backorder-customer",
            email="backorder-customer@example.com",
            password="Customer-Strong-2026!",
        )
        self.client.force_login(customer)
        product = self.create_dry_product(slug="backordered-stock", stock_quantity=0)

        create_response = self.post_order(
            {
                **self.payload,
                "email": customer.email,
                "delivery_slot": Order.DeliverySlot.COURIER,
                "items": [{"id": product.slug, "quantity": 5}],
            }
        )

        self.assertEqual(create_response.status_code, 201)
        order = Order.objects.get()
        restock_request = InventoryRestockRequest.objects.get(product=product)
        self.assertEqual(restock_request.requested_quantity, 5)

        cancel_response = self.client.post(
            reverse("orders:customer_cancel", args=[order.pk]),
            {"reason": "Khách đổi ý"},
        )

        self.assertEqual(cancel_response.status_code, 302)
        restock_request.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(restock_request.status, InventoryRestockRequest.Status.CANCELLED)
        self.assertEqual(product.stock_quantity, 0)
        send_mail.assert_called_once()

    def test_create_order_ignores_client_price_and_applies_free_shipping_threshold(self):
        self.product.price = Decimal("150000.00")
        self.product.save(update_fields=["price"])
        payload = {**self.payload, "items": [{"id": self.product.slug, "quantity": 2, "price": 1}]}

        response = self.post_order(payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.get().subtotal, Decimal("300000.00"))
        self.assertEqual(Order.objects.get().shipping_fee, Decimal("0.00"))

    def test_dry_goods_order_uses_destination_and_total_shipping_weight(self):
        product = Product.objects.create(
            sku="FM-DRY-001",
            slug="hat-dieu",
            name="Hạt điều",
            category=Product.Category.DRY_GOODS,
            description="Hạt điều rang",
            price=Decimal("80000.00"),
            stock_quantity=10,
            shipping_weight_grams=500,
            expiry_date=timezone.localdate() + timedelta(days=180),
        )
        payload = {
            **self.payload,
            "city": "Hà Nội",
            "delivery_slot": Order.DeliverySlot.COURIER,
            "items": [{"id": product.slug, "quantity": 3}],
        }

        response = self.post_order(payload)

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        self.assertEqual(order.shipping_fee, Decimal("40000.00"))
        self.assertTrue(order.is_dry_goods_order)
        self.assertEqual(order.items.get().shipping_weight_grams, 500)
        self.assertEqual(response.json()["delivery_type"], "nationwide")

    def test_dry_goods_order_accepts_hcm_and_applies_local_weight_rate(self):
        product = Product.objects.create(
            sku="FM-DRY-002",
            slug="yen-mach",
            name="Yến mạch",
            category=Product.Category.DRY_GOODS,
            description="Yến mạch",
            price=Decimal("80000.00"),
            stock_quantity=10,
            shipping_weight_grams=750,
        )
        payload = {
            **self.payload,
            "delivery_slot": Order.DeliverySlot.COURIER,
            "items": [{"id": product.slug, "quantity": 2}],
        }

        response = self.post_order(payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.get().shipping_fee, Decimal("25000.00"))

    def test_fresh_food_order_outside_hcm_is_rejected(self):
        response = self.post_order({**self.payload, "city": "Hà Nội"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_dry_goods_order_rejects_dates_after_five_days(self):
        product = Product.objects.create(
            sku="FM-DRY-003",
            slug="hat-hanh-nhan",
            name="Hạnh nhân",
            category=Product.Category.DRY_GOODS,
            description="Hạnh nhân",
            price=Decimal("90000.00"),
            stock_quantity=10,
            shipping_weight_grams=500,
        )
        payload = {
            **self.payload,
            "delivery_slot": Order.DeliverySlot.COURIER,
            "delivery_date": (timezone.localdate() + timedelta(days=6)).isoformat(),
            "items": [{"id": product.slug, "quantity": 1}],
        }

        response = self.post_order(payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_dry_goods_order_requires_courier_delivery_slot(self):
        product = Product.objects.create(
            sku="FM-DRY-004",
            slug="dau-phong",
            name="Đậu phộng",
            category=Product.Category.DRY_GOODS,
            description="Đậu phộng",
            price=Decimal("50000.00"),
            stock_quantity=10,
            shipping_weight_grams=500,
        )
        payload = {**self.payload, "items": [{"id": product.slug, "quantity": 1}]}

        response = self.post_order(payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_create_order_merges_duplicate_items(self):
        payload = {
            **self.payload,
            "items": [
                {"id": self.product.slug, "quantity": 1},
                {"id": self.product.slug, "quantity": 2},
            ],
        }

        response = self.post_order(payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(OrderItem.objects.get().quantity, 3)

    def test_authenticated_checkout_attaches_order_to_customer_account(self):
        customer = User.objects.create_user(
            username="order-customer",
            email="order-customer@example.com",
            password="Customer-Strong-2026!",
        )
        self.client.force_login(customer)

        response = self.post_order()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.get().customer, customer)

    def test_completed_order_awards_points_once_and_cancellation_reverses_them(self):
        customer = User.objects.create_user(
            username="points-customer",
            email="points-customer@example.com",
        )
        order = Order.objects.create(
            customer=customer,
            customer_name="Nguyen Van A",
            customer_email=customer.email,
            customer_phone="0901234567",
            address="12 Đường X",
            district="Quận 1",
            city="TP Hồ Chí Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            subtotal=Decimal("209999.00"),
            shipping_fee=Decimal("20000.00"),
            total=Decimal("229999.00"),
        )

        order.status = Order.Status.DELIVERED
        order.save(update_fields=["status"])
        order.status = Order.Status.DELIVERED
        order.save(update_fields=["status"])

        earned = PointsTransaction.objects.get(
            order=order,
            kind=PointsTransaction.Kind.EARNED,
        )
        self.assertEqual(earned.points, 20)
        self.assertEqual(customer.points_transactions.count(), 1)

        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
        order.save(update_fields=["status"])

        self.assertEqual(
            sum(customer.points_transactions.values_list("points", flat=True)),
            0,
        )
        self.assertEqual(
            PointsTransaction.objects.get(
                order=order,
                kind=PointsTransaction.Kind.REVERSAL,
            ).points,
            -20,
        )

    def test_unavailable_or_unknown_product_does_not_create_order(self):
        self.product.is_available = False
        self.product.save(update_fields=["is_available"])

        response = self.post_order()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_order_data_is_rejected(self):
        invalid_payloads = [
            {**self.payload, "email": "not-an-email"},
            {**self.payload, "delivery_date": (timezone.localdate() - timedelta(days=1)).isoformat()},
            {**self.payload, "delivery_slot": "midnight"},
            {**self.payload, "items": [{"id": self.product.slug, "quantity": 0}]},
            {**self.payload, "payment": "online"},
            {**self.payload, "payment": Order.PaymentMethod.VNPAY},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.post_order(payload)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_cod_order_is_created_without_online_payment_transaction(self):
        response = self.post_order({**self.payload, "payment": Order.PaymentMethod.COD})

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get()
        self.assertEqual(order.payment_method, Order.PaymentMethod.COD)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertFalse(PaymentTransaction.objects.filter(order=order).exists())
        self.assertNotIn("payment_url", response.json())

    @override_settings(
        MOMO_ENABLED=True,
        MOMO_PARTNER_CODE="MOMO123",
        MOMO_ACCESS_KEY="momo-access",
        MOMO_SECRET_KEY="momo-secret",
        MOMO_CREATE_PAYMENT_URL="https://sandbox.example/momo",
        MOMO_PUBLIC_BASE_URL="https://fitmeal-demo.example",
    )
    @patch("apps.payments.gateway.urlopen")
    def test_momo_checkout_redirects_to_local_qr_instructions(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(
            {"resultCode": 0, "payUrl": "https://sandbox.example/pay?token=sample"}
        ).encode()

        order_response = self.post_order(
            {**self.payload, "payment": Order.PaymentMethod.MOMO}
        )

        self.assertEqual(order_response.status_code, 201)
        payment = PaymentTransaction.objects.get(
            order__order_number=order_response.json()["order_number"]
        )
        self.assertIn(
            reverse(
                "payments:momo_payment_instructions",
                args=[payment.transaction_ref],
            ),
            order_response.json()["payment_url"],
        )
        instructions_response = self.client.get(order_response.json()["payment_url"])
        self.assertEqual(instructions_response.status_code, 200)
        self.assertContains(instructions_response, "data:image/svg+xml;base64,")
        self.assertContains(instructions_response, "Tóm tắt đơn hàng")
        self.assertContains(instructions_response, "2 × Whey")
        self.assertContains(instructions_response, "Cần thanh toán")
        self.assertNotContains(instructions_response, "Chỉ trong bản vẽ")

    @override_settings(
        MOMO_ENABLED=True,
        MOMO_PARTNER_CODE="MOMO123",
        MOMO_ACCESS_KEY="momo-access",
        MOMO_SECRET_KEY="momo-secret",
        MOMO_CREATE_PAYMENT_URL="https://sandbox.example/momo",
        MOMO_PUBLIC_BASE_URL="https://fitmeal-demo.example",
    )
    @patch("apps.payments.gateway.urlopen", side_effect=TimeoutError)
    def test_momo_gateway_timeout_rolls_back_order_and_inventory(self, _urlopen):
        response = self.post_order({**self.payload, "payment": Order.PaymentMethod.MOMO})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    def test_tracking_token_returns_order_status_without_customer_contact_data(self):
        create_response = self.post_order()
        token = create_response.json()["tracking_token"]

        response = self.client.get(reverse("orders:track", args=[token]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["order_number"], Order.objects.get().order_number)
        self.assertEqual(response.json()["status"], Order.Status.PENDING)
        self.assertNotIn("customer_email", response.json())
        self.assertNotIn("address", response.json())

    def test_tracking_reports_delivery_failure_and_only_customer_cancellation_progress(self):
        create_response = self.post_order()
        order = Order.objects.get()
        order.status = Order.Status.DELIVERY_ISSUE
        order.save(update_fields=["status"])
        token = create_response.json()["tracking_token"]
        request = OrderCancellationRequest.objects.create(
            order=order,
            source=OrderCancellationRequest.Source.STAFF,
            status=OrderCancellationRequest.Status.MANAGER_REVIEW,
            reason="Kiểm tra nội bộ",
        )

        response = self.client.get(reverse("orders:track", args=[token]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status_display"], "Giao hàng không thành công")
        self.assertFalse(response.json()["cancellation_requested"])

        request.source = OrderCancellationRequest.Source.CUSTOMER
        request.save(update_fields=["source"])
        response = self.client.get(reverse("orders:track", args=[token]))

        self.assertTrue(response.json()["cancellation_requested"])

    def test_tracking_page_includes_csrf_protected_delivery_response_forms(self):
        response = self.client.get(reverse("core:tracking"))

        self.assertContains(response, 'data-tracking-confirmation-form')
        self.assertContains(response, 'data-tracking-issue-form')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_tracking_delivery_action_requires_csrf_token(self):
        order, token = self.create_awaiting_confirmation_order()
        csrf_client = Client(enforce_csrf_checks=True)
        action_url = reverse("orders:track_confirm_delivery", args=[token])

        rejected_response = csrf_client.post(action_url)
        self.assertEqual(rejected_response.status_code, 403)

        page_response = csrf_client.get(reverse("core:tracking"))
        csrf_token = csrf_client.cookies["csrftoken"].value
        accepted_response = csrf_client.post(
            action_url,
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(page_response.status_code, 200)
        self.assertEqual(accepted_response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)

    def test_tracking_token_can_confirm_delivery(self):
        order, token = self.create_awaiting_confirmation_order()

        response = self.client.post(reverse("orders:track_confirm_delivery", args=[token]))

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(
            order.delivery_confirmation_method,
            Order.DeliveryConfirmationMethod.CUSTOMER,
        )

    def test_tracking_token_can_report_delivery_issue(self):
        order, token = self.create_awaiting_confirmation_order()

        response = self.client.post(
            reverse("orders:track_report_delivery_issue", args=[token]),
            {"details": "Tôi chưa nhận được đơn hàng"},
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        issue = DeliveryIssue.objects.get(order=order)
        self.assertEqual(order.status, Order.Status.DELIVERY_ISSUE)
        self.assertEqual(issue.details, "Tôi chưa nhận được đơn hàng")
        self.assertIsNone(issue.reported_by)

    def test_tracking_confirmation_after_deadline_is_automatic(self):
        order, token = self.create_awaiting_confirmation_order()
        order.delivery_confirmation_deadline = timezone.now() - timedelta(seconds=1)
        order.save(update_fields=["delivery_confirmation_deadline"])

        response = self.client.post(reverse("orders:track_confirm_delivery", args=[token]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("tự xác nhận", response.json()["message"])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(
            order.delivery_confirmation_method,
            Order.DeliveryConfirmationMethod.AUTOMATIC,
        )

    def test_tracking_token_cannot_confirm_order_outside_confirmation_status(self):
        create_response = self.post_order()
        token = create_response.json()["tracking_token"]

        response = self.client.post(reverse("orders:track_confirm_delivery", args=[token]))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Order.objects.get().status, Order.Status.PENDING)

    def test_delivered_order_encrypts_customer_details_and_only_tracks_order_code(self):
        customer = User.objects.create_user(
            username="delivered-order-customer",
            email=self.payload["email"],
            password="Customer-Strong-2026!",
        )
        self.client.force_login(customer)
        create_response = self.post_order()
        self.assertEqual(create_response.status_code, 201)
        order = Order.objects.get()
        cancellation = OrderCancellationRequest.objects.create(
            order=order,
            source=OrderCancellationRequest.Source.CUSTOMER,
            status=OrderCancellationRequest.Status.WITHDRAWN,
            reason="Khách xin lưu số điện thoại 0901234567",
            requested_by=customer,
            contact_notes="Đã gọi khách ở địa chỉ giao hàng",
        )

        order.status = Order.Status.DELIVERED
        order.save(update_fields=["status"])
        order.refresh_from_db()
        cancellation.refresh_from_db()

        self.assertTrue(order.customer_info_redacted)
        self.assertEqual(order.customer_id, customer.pk)
        self.assertEqual(order.customer_name, "")
        self.assertEqual(order.customer_email, "")
        self.assertEqual(order.customer_phone, "")
        self.assertEqual(order.address, "")
        self.assertEqual(order.district, self.payload["district"])
        self.assertEqual(order.city, self.payload["city"])
        self.assertEqual(order.note, "")
        self.assertNotIn(self.payload["email"], order.customer_pii_encrypted)
        self.assertNotIn(self.payload["phone"], order.customer_pii_encrypted)
        self.assertEqual(cancellation.reason, "")
        self.assertEqual(cancellation.contact_notes, "")
        self.assertIsNone(cancellation.requested_by)

        tracking_response = self.client.get(
            reverse("orders:track", args=[create_response.json()["tracking_token"]])
        )
        self.assertEqual(
            set(tracking_response.json()),
            {"order_number", "status", "status_display", "privacy_redacted"},
        )
        self.assertEqual(tracking_response.json()["order_number"], order.order_number)
        self.assertTrue(tracking_response.json()["privacy_redacted"])

    def test_unknown_tracking_token_returns_not_found(self):
        response = self.client.get(reverse("orders:track", args=["00000000-0000-0000-0000-000000000000"]))

        self.assertEqual(response.status_code, 404)

    def test_order_creation_requires_post_and_csrf(self):
        get_response = self.client.get(reverse("orders:create"))
        csrf_client = Client(enforce_csrf_checks=True)
        post_response = csrf_client.post(
            reverse("orders:create"),
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        self.assertEqual(get_response.status_code, 405)
        self.assertEqual(post_response.status_code, 403)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_form_can_create_order_with_its_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.get(reverse("core:checkout"))
        csrf_token = csrf_client.cookies["csrftoken"].value

        response = csrf_client.post(
            reverse("orders:create"),
            data=json.dumps(self.payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Order.objects.count(), 1)


class OrderAdminTests(TestCase):
    def test_order_is_registered_for_staff_order_processing(self):
        order_admin = admin.site._registry[Order]

        self.assertIsInstance(order_admin, OrderAdmin)
        self.assertNotIn("status", order_admin.list_editable)
        self.assertIn("status", order_admin.readonly_fields)
        self.assertIn("customer_phone", order_admin.search_fields)

    def test_django_admin_does_not_allow_status_edits_without_workflow(self):
        admin_user = User.objects.create_superuser(
            username="order-admin",
            email="order-admin@example.com",
            password="Admin-Strong-2026!",
        )
        order = Order.objects.create(
            customer_name="Nguyen Van A",
            customer_email="customer@example.com",
            customer_phone="0901234567",
            address="12 Duong X",
            district="Quan 1",
            city="TP Ho Chi Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            subtotal=Decimal("100000.00"),
            shipping_fee=Decimal("20000.00"),
            total=Decimal("120000.00"),
        )
        self.client.force_login(admin_user)
        changelist_url = reverse("admin:orders_order_changelist")

        response = self.client.get(changelist_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="form-0-status"')
        self.assertContains(response, order.order_number)

    def test_delivered_order_admin_page_hides_customer_and_delivery_details(self):
        admin_user = User.objects.create_superuser(
            username="privacy-admin",
            email="privacy-admin@example.com",
            password="Admin-Strong-2026!",
        )
        order = Order.objects.create(
            customer_name="Nguyen Van A",
            customer_email="customer@example.com",
            customer_phone="0901234567",
            address="12 Duong X",
            district="Quan 1",
            city="TP Ho Chi Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            status=Order.Status.DELIVERED,
            subtotal=Decimal("100000.00"),
            shipping_fee=Decimal("20000.00"),
            total=Decimal("120000.00"),
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:orders_order_change", args=[order.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Đã mã hóa và ẩn theo chính sách thời hạn lưu trữ.")
        for personal_data in ("Nguyen Van A", "customer@example.com", "0901234567", "12 Duong X"):
            with self.subTest(personal_data=personal_data):
                self.assertNotContains(response, personal_data)

    def test_cancelled_order_admin_page_hides_customer_and_delivery_details(self):
        admin_user = User.objects.create_superuser(
            username="cancelled-privacy-admin",
            email="cancelled-privacy-admin@example.com",
            password="Admin-Strong-2026!",
        )
        order = Order.objects.create(
            customer_name="Cancelled Customer",
            customer_email="cancelled-customer@example.com",
            customer_phone="0912345678",
            address="99 Private Road",
            district="Quan 1",
            city="TP Ho Chi Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            status=Order.Status.CANCELLED,
            subtotal=Decimal("100000.00"),
            shipping_fee=Decimal("20000.00"),
            total=Decimal("120000.00"),
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("admin:orders_order_change", args=[order.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(order.customer_info_redacted)
        self.assertContains(response, "Đã mã hóa và ẩn theo chính sách thời hạn lưu trữ.")
        for personal_data in (
            "Cancelled Customer",
            "cancelled-customer@example.com",
            "0912345678",
            "99 Private Road",
        ):
            with self.subTest(personal_data=personal_data):
                self.assertNotContains(response, personal_data)

    def test_privacy_data_migration_encrypts_existing_delivered_orders(self):
        customer = User.objects.create_user(
            username="migrated-order-customer",
            email="migration-customer@example.com",
            password="Customer-Strong-2026!",
        )
        order = Order.objects.create(
            customer=customer,
            customer_name="Nguyen Van A",
            customer_email=customer.email,
            customer_phone="0901234567",
            address="12 Duong X",
            district="Quan 1",
            city="TP Ho Chi Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            subtotal=Decimal("100000.00"),
            shipping_fee=Decimal("20000.00"),
            total=Decimal("120000.00"),
        )
        cancellation = OrderCancellationRequest.objects.create(
            order=order,
            source=OrderCancellationRequest.Source.CUSTOMER,
            status=OrderCancellationRequest.Status.WITHDRAWN,
            reason="Khách xin lưu số điện thoại 0901234567",
            requested_by=customer,
            contact_notes="Đã gọi khách ở địa chỉ giao hàng",
        )
        Order.objects.filter(pk=order.pk).update(status=Order.Status.DELIVERED)
        migration = import_module("apps.orders.migrations.0005_order_customer_pii_encrypted")

        migration.encrypt_delivered_orders(
            apps,
            SimpleNamespace(connection=connection),
        )
        order.refresh_from_db()
        cancellation.refresh_from_db()

        self.assertTrue(order.customer_pii_encrypted)
        self.assertEqual(order.customer_email, "")
        self.assertEqual(order.customer_phone, "")
        self.assertNotIn(customer.email, order.customer_pii_encrypted)
        self.assertEqual(cancellation.reason, "")
        self.assertEqual(cancellation.contact_notes, "")
        self.assertIsNone(cancellation.requested_by)

    def test_privacy_data_migration_encrypts_existing_cancelled_orders(self):
        customer = User.objects.create_user(
            username="migrated-cancelled-customer",
            email="cancelled-migration@example.com",
            password="Customer-Strong-2026!",
        )
        order = Order.objects.create(
            customer=customer,
            customer_name="Cancelled Customer",
            customer_email=customer.email,
            customer_phone="0912345678",
            address="99 Private Road",
            district="Quan 1",
            city="TP Ho Chi Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            subtotal=Decimal("100000.00"),
            shipping_fee=Decimal("20000.00"),
            total=Decimal("120000.00"),
        )
        cancellation = OrderCancellationRequest.objects.create(
            order=order,
            source=OrderCancellationRequest.Source.CUSTOMER,
            status=OrderCancellationRequest.Status.APPROVED,
            reason="Khách xin hủy, số điện thoại 0912345678",
            requested_by=customer,
            contact_notes="Đã trao đổi tại 99 Private Road",
        )
        issue = DeliveryIssue.objects.create(
            order=order,
            details="Gọi khách qua số 0912345678",
            reported_by=customer,
        )
        Order.objects.filter(pk=order.pk).update(status=Order.Status.CANCELLED)
        migration = import_module("apps.orders.migrations.0007_encrypt_cancelled_order_pii")

        migration.encrypt_cancelled_orders(
            apps,
            SimpleNamespace(connection=connection),
        )

        order.refresh_from_db()
        cancellation.refresh_from_db()
        issue.refresh_from_db()
        self.assertTrue(order.customer_info_redacted)
        self.assertEqual(order.customer_email, "")
        self.assertEqual(order.customer_phone, "")
        self.assertEqual(order.address, "")
        self.assertNotIn(customer.email, order.customer_pii_encrypted)
        self.assertNotIn("0912345678", order.customer_pii_encrypted)
        self.assertEqual(cancellation.reason, "")
        self.assertEqual(cancellation.contact_notes, "")
        self.assertIsNone(cancellation.requested_by)
        self.assertEqual(issue.details, "")
        self.assertIsNone(issue.reported_by)


class StaffOrderDashboardTests(TestCase):
    def create_order(self, *, status, total, customer=None):
        return Order.objects.create(
            customer=customer,
            customer_name="Nguyen Van A",
            customer_email="customer@example.com",
            customer_phone="0901234567",
            address="12 Duong X",
            district="Quan 1",
            city="TP Ho Chi Minh",
            delivery_region=Order.DeliveryRegion.HO_CHI_MINH_CITY,
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            status=status,
            subtotal=total,
            shipping_fee=Decimal("0.00"),
            total=total,
        )

    def test_staff_dashboard_shows_real_totals_and_order_controls(self):
        pending_order = self.create_order(status=Order.Status.PENDING, total=Decimal("120000.00"))
        self.create_order(status=Order.Status.DELIVERED, total=Decimal("80000.00"))
        self.create_order(status=Order.Status.CANCELLED, total=Decimal("50000.00"))
        admin_user = User.objects.create_superuser(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("staff_orders:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["order_count"], 3)
        self.assertEqual(response.context["pending_count"], 1)
        self.assertEqual(response.context["active_order_value"], Decimal("200000.00"))
        self.assertEqual(response.context["completed_revenue"], Decimal("80000.00"))
        self.assertContains(response, "Tổng quan")
        self.assertContains(response, "Đơn chờ xác nhận")
        self.assertNotContains(response, "Giỏ hàng")
        self.assertNotContains(response, "Django")

        order_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"section": "orders", "order": str(pending_order.pk)},
        )
        self.assertContains(order_response, "Quản lý đơn hàng")
        self.assertContains(order_response, "Lưu trạng thái")
        self.assertContains(order_response, "Xác nhận đơn")

    def test_payments_dashboard_shows_vnpay_transaction_state(self):
        order = self.create_order(
            status=Order.Status.PENDING,
            total=Decimal("120000.00"),
        )
        PaymentTransaction.objects.create(
            order=order,
            transaction_ref="FMTEST123",
            amount=order.total,
            status=PaymentTransaction.Status.PENDING,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        admin_user = User.objects.create_superuser(
            username="payment-dashboard-admin",
            email="payment-dashboard-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"section": "payments"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FMTEST123")
        self.assertContains(response, "Chờ thanh toán")
        self.assertContains(response, "Giao dịch thanh toán")

    def test_staff_order_details_hide_customer_data_after_delivery(self):
        order = self.create_order(status=Order.Status.DELIVERED, total=Decimal("80000.00"))
        cancelled_order = self.create_order(
            status=Order.Status.CANCELLED,
            total=Decimal("50000.00"),
        )
        admin_user = User.objects.create_superuser(
            username="privacy-dashboard-admin",
            email="privacy-dashboard-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        for terminal_order in (order, cancelled_order):
            with self.subTest(status=terminal_order.status):
                response = self.client.get(
                    reverse("staff_orders:dashboard"),
                    {"section": "orders", "order": str(terminal_order.pk)},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    "Thông tin khách hàng đã được mã hóa và ẩn sau khi đơn hoàn tất hoặc bị hủy.",
                )
                for personal_data in (
                    "Nguyen Van A",
                    "customer@example.com",
                    "0901234567",
                    "12 Duong X",
                ):
                    with self.subTest(personal_data=personal_data):
                        self.assertNotContains(response, personal_data)

    def test_employee_order_search_hides_customer_data_for_cancelled_orders(self):
        order = self.create_order(
            status=Order.Status.CANCELLED,
            total=Decimal("50000.00"),
        )
        employee = User.objects.create_user(
            username="cancelled-order-employee",
            email="cancelled-order-employee@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(employee)

        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "orders", "q": order.order_number},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thông tin khách hàng đã được mã hóa và ẩn sau khi đơn kết thúc.")
        self.assertContains(response, 'class="employee-order-terminal-status is-cancelled">Đơn hủy</p>')
        for personal_data in ("Nguyen Van A", "customer@example.com", "0901234567", "12 Duong X"):
            with self.subTest(personal_data=personal_data):
                self.assertNotContains(response, personal_data)

    def test_employee_order_search_marks_completed_orders_in_green(self):
        order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("80000.00"),
        )
        employee = User.objects.create_user(
            username="completed-order-employee",
            email="completed-order-employee@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(employee)

        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "orders", "q": order.order_number},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="employee-order-terminal-status is-completed">Hoàn tất</p>')

    def test_customer_order_history_shows_cancel_actions_for_cancellable_orders(self):
        customer = User.objects.create_user(
            username="customer-cancel-actions",
            email="customer-cancel-actions@example.com",
            password="Customer-Strong-2026!",
        )
        self.create_order(
            status=Order.Status.PENDING,
            total=Decimal("120000.00"),
            customer=customer,
        )
        self.create_order(
            status=Order.Status.PACKING,
            total=Decimal("80000.00"),
            customer=customer,
        )
        self.client.force_login(customer)

        response = self.client.get(reverse("core:account"), {"tab": "orders"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hủy đơn")
        self.assertContains(response, "Yêu cầu hủy")
        self.assertContains(response, "data-open-cancel-dialog=")

    def test_customer_directory_hides_phone_for_staff_and_admin(self):
        customer = User.objects.create_user(
            username="private-phone-customer",
            email="private-phone@example.com",
            password="Customer-Strong-2026!",
            phone="0901234567",
        )
        manager = User.objects.create_user(
            username="phone-privacy-manager",
            email="phone-privacy-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        employee_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "customers"},
        )

        self.assertEqual(employee_response.status_code, 200)
        self.assertContains(employee_response, customer.email)
        self.assertContains(employee_response, "*******567")
        self.assertContains(employee_response, "ĐIỆN THOẠI")
        self.assertContains(employee_response, "số điện thoại")
        self.assertNotContains(employee_response, "0901234567")

        admin_user = User.objects.create_superuser(
            username="phone-privacy-admin",
            email="phone-privacy-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        admin_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"section": "customers"},
        )

        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, customer.email)
        self.assertContains(admin_response, "*******567")
        self.assertContains(admin_response, "ĐIỆN THOẠI")
        self.assertNotContains(admin_response, "0901234567")

    def test_employee_management_opens_inside_the_dashboard_section(self):
        admin_user = User.objects.create_superuser(
            username="employees-page-admin",
            email="employees-page-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"section": "employees"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_section"], "employees")
        self.assertContains(response, "Nhân viên &amp; phân quyền")
        self.assertContains(response, "Tạo tài khoản nhân viên")
        self.assertContains(response, 'id="employees"')

    def test_orders_screen_filters_and_renders_selected_order_details(self):
        order = self.create_order(status=Order.Status.PENDING, total=Decimal("120000.00"))
        OrderItem.objects.create(
            order=order,
            product_sku="FM-DETAIL-001",
            product_name="Bữa ăn FitMeal",
            unit_price=Decimal("60000.00"),
            quantity=2,
            line_total=Decimal("120000.00"),
        )
        self.create_order(status=Order.Status.DELIVERED, total=Decimal("80000.00"))
        admin_user = User.objects.create_superuser(
            username="orders-filter-admin",
            email="orders-filter-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {
                "section": "orders",
                "date_range": "all",
                "status": "pending",
                "q": "0901234567",
                "order": str(order.pk),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(response.context["selected_order"].pk, order.pk)
        self.assertContains(response, order.order_number)
        self.assertContains(response, "Bữa ăn FitMeal")
        self.assertContains(response, "Thanh toán khi nhận hàng")
        self.assertContains(response, "Chưa tích hợp hãng vận chuyển hoặc mã vận đơn.")

    def test_orders_csv_export_escapes_spreadsheet_formulas(self):
        order = self.create_order(status=Order.Status.PENDING, total=Decimal("120000.00"))
        order.customer_name = "=HYPERLINK(\"https://example.invalid\")"
        order.save(update_fields=["customer_name"])
        admin_user = User.objects.create_superuser(
            username="orders-export-admin",
            email="orders-export-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"section": "orders", "date_range": "all", "export": "orders"},
        )

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("'=HYPERLINK", response.content.decode("utf-8-sig"))

    def test_dashboard_period_metrics_and_csv_only_include_selected_period(self):
        recent_order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("90000.00"),
        )
        previous_day_order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("30000.00"),
        )
        previous_day_order.created_at = timezone.now() - timedelta(days=1)
        previous_day_order.save(update_fields=["created_at"])
        old_order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("60000.00"),
        )
        old_order.created_at = timezone.now() - timedelta(days=10)
        old_order.save(update_fields=["created_at"])
        admin_user = User.objects.create_superuser(
            username="report-admin",
            email="report-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.get(reverse("staff_orders:dashboard"), {"range": "7d"})

        self.assertEqual(response.context["period_revenue"], Decimal("120000.00"))
        self.assertEqual(response.context["period_order_count"], 2)
        self.assertEqual(sum(point["amount"] for point in response.context["chart_points"]), Decimal("120000.00"))
        chart_points = {point["day"]: point for point in response.context["chart_points"]}
        self.assertEqual(chart_points[timezone.localdate()]["height"], 100.0)
        self.assertEqual(
            chart_points[timezone.localdate() - timedelta(days=1)]["height"],
            33.3,
        )
        self.assertRegex(response.content.decode(), r'style="height:100(?:\.0)?%"')
        self.assertEqual(
            response.content.count(b'class="dashboard-chart-track"><i'),
            2,
        )

        report_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"range": "7d", "export": "csv"},
        )
        self.assertEqual(report_response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(recent_order.order_number, report_response.content.decode("utf-8-sig"))
        self.assertNotIn(old_order.order_number, report_response.content.decode("utf-8-sig"))

    def test_staff_can_confirm_order_from_custom_dashboard(self):
        order = self.create_order(status=Order.Status.PENDING, total=Decimal("120000.00"))
        admin_user = User.objects.create_superuser(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("staff_orders:update_status", args=[order.pk]),
            {"status": Order.Status.CONFIRMED},
        )

        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?section=orders&date_range=today&status=all&payment=all&q=&order={order.pk}#orders",
        )
        order.refresh_from_db()
        self.assertEqual(
            order.status,
            Order.Status.CONFIRMED,
            [str(message) for message in response.wsgi_request._messages],
        )

    def test_staff_marks_delivery_as_awaiting_customer_confirmation(self):
        order = self.create_order(status=Order.Status.DELIVERING, total=Decimal("120000.00"))
        manager = User.objects.create_user(
            username="delivery-confirmation-manager",
            email="delivery-confirmation-manager@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)
        now = timezone.now()

        self.client.post(
            reverse("staff_orders:update_status", args=[order.pk]),
            {"status": Order.Status.AWAITING_CUSTOMER_CONFIRMATION},
        )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.AWAITING_CUSTOMER_CONFIRMATION)
        self.assertGreaterEqual(order.delivery_confirmation_deadline, now + timedelta(minutes=2, seconds=55))
        self.assertLessEqual(order.delivery_confirmation_deadline, now + timedelta(minutes=3, seconds=5))

        self.client.post(
            reverse("staff_orders:update_status", args=[order.pk]),
            {"status": Order.Status.DELIVERING},
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.AWAITING_CUSTOMER_CONFIRMATION)

    def test_staff_can_mark_delivery_as_failed_when_customer_cannot_be_contacted(self):
        order = self.create_order(status=Order.Status.DELIVERING, total=Decimal("120000.00"))
        manager = User.objects.create_user(
            username="no-contact-manager",
            email="no-contact-manager@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        workspace_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "work"},
        )
        self.assertContains(workspace_response, "Không liên lạc được với khách")

        self.client.post(
            reverse("staff_orders:update_status", args=[order.pk]),
            {"status": Order.Status.DELIVERY_ISSUE},
        )

        order.refresh_from_db()
        issue = DeliveryIssue.objects.get(order=order)
        self.assertEqual(order.status, Order.Status.DELIVERY_ISSUE)
        self.assertEqual(issue.source, DeliveryIssue.Source.STAFF_DELIVERY)
        self.assertEqual(issue.details, "Không liên lạc được với khách khi giao hàng.")
        self.assertEqual(issue.reported_by, manager)

        response = self.client.get(reverse("orders:track", args=[order.tracking_token]))
        self.assertEqual(response.json()["status_display"], "Giao hàng không thành công")

        other_order = self.create_order(status=Order.Status.READY, total=Decimal("120000.00"))
        self.client.post(
            reverse("staff_orders:update_status", args=[other_order.pk]),
            {"status": Order.Status.DELIVERY_ISSUE},
        )
        other_order.refresh_from_db()
        self.assertEqual(other_order.status, Order.Status.READY)
        self.assertFalse(DeliveryIssue.objects.filter(order=other_order).exists())

    def test_customer_can_confirm_receipt_and_delivery_is_archived(self):
        customer = User.objects.create_user(
            username="confirm-delivery-customer",
            email="confirm-delivery@example.com",
            password="Customer-Strong-2026!",
        )
        order = self.create_order(
            status=Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
            total=Decimal("120000.00"),
            customer=customer,
        )
        order.delivery_confirmation_deadline = timezone.now() + timedelta(minutes=3)
        order.save(update_fields=["delivery_confirmation_deadline"])
        self.client.force_login(customer)

        response = self.client.post(
            reverse("orders:customer_confirm_delivery", args=[order.pk])
        )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(
            order.delivery_confirmation_method,
            Order.DeliveryConfirmationMethod.CUSTOMER,
        )
        self.assertTrue(order.customer_pii_encrypted)
        self.assertEqual(order.customer_name, "")

    def test_customer_confirmation_after_deadline_is_recorded_as_automatic(self):
        customer = User.objects.create_user(
            username="late-confirm-delivery-customer",
            email="late-confirm-delivery@example.com",
            password="Customer-Strong-2026!",
        )
        order = self.create_order(
            status=Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
            total=Decimal("120000.00"),
            customer=customer,
        )
        order.delivery_confirmation_deadline = timezone.now() - timedelta(seconds=1)
        order.save(update_fields=["delivery_confirmation_deadline"])
        self.client.force_login(customer)

        self.client.post(reverse("orders:customer_confirm_delivery", args=[order.pk]))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(
            order.delivery_confirmation_method,
            Order.DeliveryConfirmationMethod.AUTOMATIC,
        )

    def test_customer_delivery_issue_is_escalated_to_manager_and_can_resume_delivery(self):
        customer = User.objects.create_user(
            username="delivery-issue-customer",
            email="delivery-issue@example.com",
            password="Customer-Strong-2026!",
        )
        order = self.create_order(
            status=Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
            total=Decimal("120000.00"),
            customer=customer,
        )
        order.delivery_confirmation_deadline = timezone.now() + timedelta(minutes=3)
        order.save(update_fields=["delivery_confirmation_deadline"])
        self.client.force_login(customer)

        self.client.post(
            reverse("orders:customer_report_delivery_issue", args=[order.pk]),
            {"details": "Tôi chưa nhận được đơn hàng"},
        )

        issue = DeliveryIssue.objects.get(order=order)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERY_ISSUE)
        self.assertEqual(issue.details, "Tôi chưa nhận được đơn hàng")

        manager = User.objects.create_user(
            username="delivery-issue-manager",
            email="delivery-issue-manager@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)
        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "orders", "view": "delivery_issues"},
        )
        self.assertContains(response, issue.details)

        self.client.post(
            reverse("staff_orders:resolve_delivery_issue", args=[issue.pk]),
            {"decision": DeliveryIssue.Resolution.REDELIVER, "resolution": "Tiếp tục giao đến khách"},
        )

        order.refresh_from_db()
        issue.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERING)
        self.assertEqual(issue.status, DeliveryIssue.Status.RESOLVED)

    def test_customer_cannot_report_delivery_issue_after_confirmation_deadline(self):
        customer = User.objects.create_user(
            username="late-delivery-issue-customer",
            email="late-delivery-issue@example.com",
            password="Customer-Strong-2026!",
        )
        order = self.create_order(
            status=Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
            total=Decimal("120000.00"),
            customer=customer,
        )
        order.delivery_confirmation_deadline = timezone.now() - timedelta(seconds=1)
        order.save(update_fields=["delivery_confirmation_deadline"])
        self.client.force_login(customer)

        self.client.post(
            reverse("orders:customer_report_delivery_issue", args=[order.pk]),
            {"details": "Tôi chưa nhận được đơn hàng"},
        )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(
            order.delivery_confirmation_method,
            Order.DeliveryConfirmationMethod.AUTOMATIC,
        )
        self.assertFalse(DeliveryIssue.objects.filter(order=order).exists())

    def test_manager_can_resolve_delivery_issue_as_received_and_archive_issue_details(self):
        customer = User.objects.create_user(
            username="delivery-confirmed-issue-customer",
            email="delivery-confirmed-issue@example.com",
            password="Customer-Strong-2026!",
        )
        order = self.create_order(
            status=Order.Status.DELIVERY_ISSUE,
            total=Decimal("120000.00"),
            customer=customer,
        )
        issue = DeliveryIssue.objects.create(
            order=order,
            details="Khách báo chưa nhận hàng",
            reported_by=customer,
        )
        manager = User.objects.create_user(
            username="delivery-confirmed-issue-manager",
            email="delivery-confirmed-issue-manager@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        self.client.post(
            reverse("staff_orders:resolve_delivery_issue", args=[issue.pk]),
            {
                "decision": DeliveryIssue.Resolution.CONFIRMED,
                "resolution": "Đã kiểm tra với khách và xác nhận đã nhận",
            },
        )

        order.refresh_from_db()
        issue.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(order.delivery_confirmation_method, Order.DeliveryConfirmationMethod.MANAGER)
        self.assertTrue(order.customer_pii_encrypted)
        self.assertEqual(issue.details, "")
        self.assertEqual(issue.resolution, "")
        self.assertIsNone(issue.reported_by)

    def test_manager_workspace_separates_failed_deliveries_from_customer_complaints(self):
        manager = User.objects.create_user(
            username="separate-delivery-queues-manager",
            email="separate-delivery-queues@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        customer = User.objects.create_user(
            username="separate-delivery-queues-customer",
            email="separate-delivery-queues-customer@example.com",
            password="Customer-Strong-2026!",
        )
        failed_order = self.create_order(
            status=Order.Status.DELIVERY_ISSUE,
            total=Decimal("120000.00"),
        )
        failed_issue = DeliveryIssue.objects.create(
            order=failed_order,
            source=DeliveryIssue.Source.STAFF_DELIVERY,
            details="Không liên lạc được với khách khi giao hàng.",
            reported_by=manager,
        )
        complaint_order = self.create_order(
            status=Order.Status.DELIVERY_ISSUE,
            total=Decimal("90000.00"),
        )
        complaint_issue = DeliveryIssue.objects.create(
            order=complaint_order,
            details="Khách báo chưa nhận được đơn.",
            reported_by=customer,
        )
        self.client.force_login(manager)

        failure_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "orders", "view": "delivery_failures"},
        )
        self.assertEqual(failure_response.status_code, 200)
        self.assertEqual(failure_response.context["pending_delivery_failure_count"], 1)
        self.assertEqual(failure_response.context["pending_customer_complaint_count"], 1)
        self.assertContains(failure_response, failed_issue.details)
        self.assertNotContains(failure_response, complaint_issue.details)
        self.assertContains(failure_response, "Khiếu nại khách hàng")

        complaint_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "orders", "view": "delivery_issues"},
        )
        self.assertEqual(complaint_response.status_code, 200)
        self.assertContains(complaint_response, complaint_issue.details)
        self.assertNotContains(complaint_response, failed_issue.details)

    def test_manager_can_record_contact_success_for_failed_delivery(self):
        manager = User.objects.create_user(
            username="failed-delivery-contact-manager",
            email="failed-delivery-contact@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        order = self.create_order(
            status=Order.Status.DELIVERY_ISSUE,
            total=Decimal("120000.00"),
        )
        issue = DeliveryIssue.objects.create(
            order=order,
            source=DeliveryIssue.Source.STAFF_DELIVERY,
            details="Không liên lạc được với khách khi giao hàng.",
            reported_by=manager,
        )
        self.client.force_login(manager)

        self.client.post(
            reverse("staff_orders:resolve_delivery_issue", args=[issue.pk]),
            {
                "decision": DeliveryIssue.Resolution.CONTACTED,
                "resolution": "Đã liên hệ được, thống nhất giao lại trong ngày.",
            },
        )

        order.refresh_from_db()
        issue.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERING)
        self.assertEqual(issue.status, DeliveryIssue.Status.RESOLVED)
        self.assertEqual(issue.resolution_outcome, DeliveryIssue.Resolution.CONTACTED)

    def test_manager_cancelling_failed_delivery_requests_manual_refund_for_paid_order(self):
        manager = User.objects.create_user(
            username="failed-delivery-cancel-manager",
            email="failed-delivery-cancel@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        order = self.create_order(
            status=Order.Status.DELIVERY_ISSUE,
            total=Decimal("120000.00"),
        )
        order.payment_method = Order.PaymentMethod.BANK_TRANSFER
        order.save(update_fields=["payment_method"])
        payment = PaymentTransaction.objects.create(
            order=order,
            transaction_ref="FAILED-DELIVERY-PAID",
            amount=order.total,
            status=PaymentTransaction.Status.PAID,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        issue = DeliveryIssue.objects.create(
            order=order,
            source=DeliveryIssue.Source.STAFF_DELIVERY,
            details="Không liên lạc được với khách khi giao hàng.",
            reported_by=manager,
        )
        self.client.force_login(manager)

        self.client.post(
            reverse("staff_orders:resolve_delivery_issue", args=[issue.pk]),
            {
                "decision": DeliveryIssue.Resolution.CANCELLED,
                "resolution": "Đã gọi nhiều lần nhưng không liên lạc được.",
            },
        )

        order.refresh_from_db()
        issue.refresh_from_db()
        payment.refresh_from_db()
        cancellation = OrderCancellationRequest.objects.get(order=order)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(order.refund_status, Order.RefundStatus.REQUESTED)
        self.assertEqual(payment.status, PaymentTransaction.Status.PAID)
        self.assertEqual(issue.resolution_outcome, DeliveryIssue.Resolution.CANCELLED)
        self.assertEqual(cancellation.status, OrderCancellationRequest.Status.APPROVED)

    def test_customer_complaint_cannot_be_cancelled_from_delivery_issue_form(self):
        customer = User.objects.create_user(
            username="complaint-not-cancellable-customer",
            email="complaint-not-cancellable@example.com",
            password="Customer-Strong-2026!",
        )
        manager = User.objects.create_user(
            username="complaint-not-cancellable-manager",
            email="complaint-not-cancellable-manager@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        order = self.create_order(
            status=Order.Status.DELIVERY_ISSUE,
            total=Decimal("120000.00"),
        )
        issue = DeliveryIssue.objects.create(
            order=order,
            details="Khách báo chưa nhận hàng.",
            reported_by=customer,
        )
        self.client.force_login(manager)

        self.client.post(
            reverse("staff_orders:resolve_delivery_issue", args=[issue.pk]),
            {
                "decision": DeliveryIssue.Resolution.CANCELLED,
                "resolution": "Không liên lạc được.",
            },
        )

        order.refresh_from_db()
        issue.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERY_ISSUE)
        self.assertEqual(issue.status, DeliveryIssue.Status.PENDING)

    def test_expired_delivery_confirmation_is_automatically_finalized(self):
        order = self.create_order(
            status=Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
            total=Decimal("120000.00"),
        )
        order.delivery_confirmation_deadline = timezone.now() - timedelta(seconds=1)
        order.save(update_fields=["delivery_confirmation_deadline"])
        now = timezone.now()

        finalized = finalize_expired_delivery_confirmations(now=now)

        order.refresh_from_db()
        self.assertEqual(finalized, 1)
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(
            order.delivery_confirmation_method,
            Order.DeliveryConfirmationMethod.AUTOMATIC,
        )
        self.assertEqual(order.delivery_confirmed_at, now)
        self.assertIsNone(order.delivery_confirmation_deadline)
        self.assertTrue(order.customer_pii_encrypted)

    def test_staff_cannot_cancel_order_after_it_is_out_for_delivery(self):
        order = self.create_order(status=Order.Status.DELIVERING, total=Decimal("120000.00"))
        admin_user = User.objects.create_superuser(
            username="delivery-admin",
            email="delivery-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        self.client.post(
            reverse("staff_orders:update_status", args=[order.pk]),
            {"status": Order.Status.CANCELLED},
        )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERING)

    def test_customer_cannot_open_or_update_staff_dashboard(self):
        customer = User.objects.create_user(
            username="dashboard-customer",
            email="dashboard-customer@example.com",
            password="Customer-Strong-2026!",
        )
        order = self.create_order(status=Order.Status.PENDING, total=Decimal("120000.00"))
        self.client.force_login(customer)

        response = self.client.get(reverse("staff_orders:dashboard"))

        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse("staff_orders:update_status", args=[order.pk]),
            {"status": Order.Status.CONFIRMED},
        )
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_employee_without_workspace_role_is_denied(self):
        employee = User.objects.create_user(
            username="dashboard-employee",
            email="dashboard-employee@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
        )
        order = self.create_order(status=Order.Status.PENDING, total=Decimal("120000.00"))
        self.client.force_login(employee)

        response = self.client.get(reverse("staff_orders:dashboard"))
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse("staff_orders:update_status", args=[order.pk]),
            {"status": Order.Status.CONFIRMED},
        )
        self.assertEqual(response.status_code, 403)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_sales_employee_uses_workspace_and_can_advance_order_but_not_cancel(self):
        order = self.create_order(status=Order.Status.PENDING, total=Decimal("120000.00"))
        employee = User.objects.create_user(
            username="sales-employee",
            email="sales-employee@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(employee)

        response = self.client.get(reverse("staff_orders:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_workspace"], "work")
        self.assertContains(response, "Chờ xác nhận")
        self.assertContains(response, order.order_number)

        response = self.client.post(
            f"{reverse('staff_orders:update_status', args=[order.pk])}?workspace=work",
            {"status": Order.Status.CONFIRMED},
        )
        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?workspace=work#staff-workspace",
        )
        order.refresh_from_db()
        self.assertEqual(
            order.status,
            Order.Status.CONFIRMED,
            (
                f"role={response.wsgi_request.user.staff_role}, "
                f"messages={[str(message) for message in response.wsgi_request._messages]}"
            ),
        )

        self.client.post(
            f"{reverse('staff_orders:update_status', args=[order.pk])}?workspace=work",
            {"status": Order.Status.CANCELLED},
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(
            self.client.post(
                reverse("staff_orders:cancel_order", args=[order.pk]),
                {"reason": "Khách yêu cầu hủy"},
            ).status_code,
            403,
        )

    @patch("apps.orders.views.send_mail", return_value=1)
    def test_customer_can_cancel_immediately_after_employee_confirms_order(self, send_mail):
        customer = User.objects.create_user(
            username="post-confirmation-customer",
            email="post-confirmation@example.com",
            password="Customer-Strong-2026!",
        )
        employee = User.objects.create_user(
            username="post-confirmation-sales",
            email="post-confirmation-sales@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        order = self.create_order(
            status=Order.Status.CONFIRMED,
            total=Decimal("120000.00"),
            customer=customer,
        )

        self.client.force_login(customer)
        cancel_response = self.client.post(
            reverse("orders:customer_cancel", args=[order.pk]),
            {"reason": "Vừa xác nhận nhầm"},
        )

        self.assertEqual(cancel_response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        send_mail.assert_called_once()

        self.client.force_login(employee)
        late_update = self.client.post(
            reverse("staff_orders:update_status", args=[order.pk]),
            {"status": Order.Status.PREPARING},
        )

        self.assertEqual(late_update.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)

    @patch("apps.orders.views.send_mail", return_value=1)
    def test_manager_can_cancel_order_before_delivery(self, send_mail):
        order = self.create_order(status=Order.Status.PENDING, total=Decimal("120000.00"))
        manager = User.objects.create_user(
            username="orders-manager",
            email="orders-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        response = self.client.post(
            reverse("staff_orders:cancel_order", args=[order.pk]),
            {"reason": "Khách đổi ý"},
        )

        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?workspace=orders#staff-workspace",
        )
        order.refresh_from_db()
        self.assertEqual(
            order.status,
            Order.Status.CANCELLED,
            (
                f"role={response.wsgi_request.user.staff_role}, "
                f"messages={[str(message) for message in response.wsgi_request._messages]}"
            ),
        )
        self.assertTrue(order.customer_info_redacted)
        self.assertEqual(order.customer_name, "")
        self.assertEqual(order.customer_email, "")
        self.assertEqual(order.cancellation_reason, "")
        self.assertEqual(
            order.cancellation_reason_category,
            Order.CancellationReasonCategory.CUSTOMER_CHANGED_MIND,
        )
        self.assertEqual(send_mail.call_args.args[3], ["customer@example.com"])
        cancellation = OrderCancellationRequest.objects.get(order=order)
        self.assertEqual(cancellation.status, OrderCancellationRequest.Status.APPROVED)
        self.assertEqual(cancellation.reason, "")

    def test_manager_direct_cancellation_requires_reason(self):
        order = self.create_order(status=Order.Status.PENDING, total=Decimal("120000.00"))
        manager = User.objects.create_user(
            username="manager-reason",
            email="manager-reason@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        self.client.post(reverse("staff_orders:cancel_order", args=[order.pk]), {"reason": ""})

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertFalse(OrderCancellationRequest.objects.filter(order=order).exists())

    def test_manager_cannot_directly_cancel_order_already_out_for_delivery(self):
        order = self.create_order(status=Order.Status.DELIVERING, total=Decimal("120000.00"))
        manager = User.objects.create_user(
            username="manager-delivery-cancel",
            email="manager-delivery-cancel@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        self.client.post(
            reverse("staff_orders:cancel_order", args=[order.pk]),
            {"reason": "Khách gọi muốn hủy"},
        )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERING)
        self.assertFalse(OrderCancellationRequest.objects.filter(order=order).exists())

    def test_staff_cancellation_request_waits_for_manager_approval(self):
        order = self.create_order(status=Order.Status.CONFIRMED, total=Decimal("120000.00"))
        employee = User.objects.create_user(
            username="sales-cancellation",
            email="sales-cancellation@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        manager = User.objects.create_user(
            username="manager-approval",
            email="manager-approval@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(employee)

        self.client.post(
            reverse("staff_orders:request_cancellation", args=[order.pk]),
            {"reason": "Hết món trong kho"},
        )

        order.refresh_from_db()
        cancellation = OrderCancellationRequest.objects.get(order=order)
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(cancellation.status, OrderCancellationRequest.Status.MANAGER_REVIEW)

        self.client.force_login(manager)
        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "orders", "view": "cancellations"},
        )
        self.assertContains(response, order.order_number)
        self.assertContains(response, "Hết món trong kho")

        self.client.post(
            reverse("staff_orders:resolve_cancellation", args=[cancellation.pk]),
            {"decision": "approve"},
        )

        order.refresh_from_db()
        cancellation.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(
            order.cancellation_reason_category,
            Order.CancellationReasonCategory.OUT_OF_STOCK,
        )
        self.assertEqual(cancellation.status, OrderCancellationRequest.Status.APPROVED)
        self.assertTrue(order.customer_info_redacted)
        self.assertEqual(order.customer_phone, "")
        self.assertEqual(cancellation.reason, "")
        self.assertEqual(cancellation.manager_resolution_reason, "")

    @patch("apps.orders.views.send_mail", return_value=1)
    def test_manager_approval_cancels_pending_payment_with_valid_response_code(self, _send_mail):
        order = self.create_order(status=Order.Status.CONFIRMED, total=Decimal("120000.00"))
        order.payment_method = Order.PaymentMethod.MOMO
        order.save(update_fields=["payment_method"])
        payment = PaymentTransaction.objects.create(
            order=order,
            provider=PaymentTransaction.Provider.MOMO,
            transaction_ref="cancel-momo-reference",
            amount=order.total,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        cancellation = OrderCancellationRequest.objects.create(
            order=order,
            source=OrderCancellationRequest.Source.STAFF,
            status=OrderCancellationRequest.Status.MANAGER_REVIEW,
            reason="Khách yêu cầu hủy",
        )
        manager = User.objects.create_user(
            username="manager-payment-cancel",
            email="manager-payment-cancel@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        response = self.client.post(
            reverse("staff_orders:resolve_cancellation", args=[cancellation.pk]),
            {"decision": "approve"},
        )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(payment.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(payment.response_code, "CANCELLED")
        self.assertLessEqual(len(payment.response_code), 10)

    def test_staff_workspace_shows_customer_cancellation_call_queue(self):
        customer = User.objects.create_user(
            username="queue-customer",
            email="queue-customer@example.com",
            password="Customer-Strong-2026!",
        )
        order = self.create_order(
            status=Order.Status.READY,
            total=Decimal("120000.00"),
            customer=customer,
        )
        employee = User.objects.create_user(
            username="queue-employee",
            email="queue-employee@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )

        self.client.force_login(customer)
        self.client.post(
            reverse("orders:customer_cancel", args=[order.pk]),
            {"reason": "Khách đổi lịch nhận món"},
        )
        cancellation = OrderCancellationRequest.objects.get(order=order)
        self.assertEqual(cancellation.status, OrderCancellationRequest.Status.CONTACT_PENDING)

        self.client.force_login(employee)

        for workspace in ("work", "orders"):
            with self.subTest(workspace=workspace):
                response = self.client.get(
                    reverse("staff_orders:dashboard"),
                    {"workspace": workspace},
                )
                self.assertContains(response, "Yêu cầu hủy cần gọi lại")
                self.assertContains(response, "Khách đổi lịch nhận món")
                self.assertContains(response, "sẵn sàng giao")
                self.assertEqual(response.context["contact_cancellation_count"], 1)
                self.assertContains(
                    response,
                    reverse("staff_orders:record_cancellation_contact", args=[cancellation.pk]),
                )

    def test_customer_request_is_escalated_after_two_unanswered_calls(self):
        customer = User.objects.create_user(
            username="cancellation-customer",
            email="cancellation-customer@example.com",
            password="Customer-Strong-2026!",
        )
        order = self.create_order(
            status=Order.Status.PREPARING,
            total=Decimal("120000.00"),
            customer=customer,
        )
        employee = User.objects.create_user(
            username="calling-employee",
            email="calling-employee@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(customer)

        self.client.post(
            reverse("orders:customer_cancel", args=[order.pk]),
            {"reason": "Tôi không thể nhận đơn"},
        )

        cancellation = OrderCancellationRequest.objects.get(order=order)
        self.assertEqual(cancellation.status, OrderCancellationRequest.Status.CONTACT_PENDING)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PREPARING)

        self.client.force_login(employee)
        contact_url = reverse("staff_orders:record_cancellation_contact", args=[cancellation.pk])
        for attempt in range(1, 3):
            self.client.post(contact_url, {"outcome": "no_answer", "note": f"Lần gọi {attempt}"})
            cancellation.refresh_from_db()
            self.assertEqual(cancellation.contact_attempts, attempt)
            expected_status = (
                OrderCancellationRequest.Status.MANAGER_REVIEW
                if attempt == 2
                else OrderCancellationRequest.Status.CONTACT_PENDING
            )
            self.assertEqual(cancellation.status, expected_status)

        manager = User.objects.create_user(
            username="review-manager",
            email="review-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)
        self.client.post(
            reverse("staff_orders:resolve_cancellation", args=[cancellation.pk]),
            {"decision": "reject", "reason": "Đơn đã được chuẩn bị xong"},
        )
        cancellation.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(cancellation.status, OrderCancellationRequest.Status.REJECTED)
        self.assertEqual(
            cancellation.manager_resolution_reason,
            "Đơn đã được chuẩn bị xong",
        )
        self.assertEqual(order.status, Order.Status.PREPARING)

    @patch("apps.orders.views.send_mail", return_value=1)
    def test_customer_can_directly_cancel_pending_order_with_reason(self, send_mail):
        customer = User.objects.create_user(
            username="direct-cancel-customer",
            email="direct-cancel-customer@example.com",
            password="Customer-Strong-2026!",
        )
        order = self.create_order(
            status=Order.Status.PENDING,
            total=Decimal("120000.00"),
            customer=customer,
        )
        self.client.force_login(customer)

        response = self.client.post(
            reverse("orders:customer_cancel", args=[order.pk]),
            {"reason": "Đặt nhầm món"},
        )

        order.refresh_from_db()
        cancellation = OrderCancellationRequest.objects.get(order=order)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertTrue(order.customer_info_redacted)
        self.assertEqual(order.customer_name, "")
        self.assertEqual(order.customer_email, "")
        self.assertEqual(order.customer_phone, "")
        self.assertEqual(order.cancellation_reason, "")
        self.assertEqual(cancellation.status, OrderCancellationRequest.Status.APPROVED)
        self.assertEqual(cancellation.reason, "")
        self.assertIsNone(cancellation.requested_by)
        self.assertEqual(send_mail.call_args.args[3], ["customer@example.com"])

    def test_reorder_returns_only_the_customer_orders_available_items(self):
        customer = User.objects.create_user(
            username="reorder-customer",
            email="reorder-customer@example.com",
            password="Customer-Strong-2026!",
        )
        product = Product.objects.create(
            sku="FM-REORDER-001",
            slug="reorder-meal",
            name="Reorder Meal",
            category=Product.Category.MEAL,
            description="Món còn bán",
            price=Decimal("60000.00"),
            is_available=True,
        )
        order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("120000.00"),
            customer=customer,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_sku=product.sku,
            product_name=product.name,
            unit_price=product.price,
            quantity=2,
            line_total=Decimal("120000.00"),
        )
        self.client.force_login(customer)

        response = self.client.post(reverse("orders:reorder", args=[order.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [{"id": product.slug, "quantity": 2}])

        other_customer = User.objects.create_user(
            username="other-reorder-customer",
            email="other-reorder-customer@example.com",
            password="Customer-Strong-2026!",
        )
        self.client.force_login(other_customer)
        response = self.client.post(reverse("orders:reorder", args=[order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_employee_workspace_sections_render(self):
        sold_product = Product.objects.create(
            sku="FM-REPORT-001",
            slug="workspace-report-meal",
            name="Bữa ăn báo cáo",
            category=Product.Category.MEAL,
            description="Món trong báo cáo",
            price=Decimal("60000"),
        )
        delivered_order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("120000"),
        )
        OrderItem.objects.create(
            order=delivered_order,
            product=sold_product,
            product_sku=sold_product.sku,
            product_name=sold_product.name,
            product_category=sold_product.category,
            unit_price=Decimal("60000"),
            quantity=2,
            line_total=Decimal("120000"),
        )
        employee = User.objects.create_user(
            username="workspace-manager",
            email="workspace-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(employee)

        for section in (
            "work",
            "orders",
            "customers",
            "menu",
            "inventory",
            "reports",
            "activity",
            "profile",
        ):
            with self.subTest(section=section):
                response = self.client.get(
                    reverse("staff_orders:dashboard"),
                    {"workspace": section},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["active_workspace"], section)
                if section == "profile":
                    self.assertContains(response, "Quản lý món, giá và tồn kho")
                if section == "reports":
                    self.assertEqual(response.context["report_revenue"], Decimal("120000"))
                    self.assertEqual(response.context["report_completed_count"], 1)
                    self.assertEqual(
                        response.context["report_average_order_value"],
                        Decimal("120000"),
                    )
                    self.assertEqual(
                        response.context["report_category_rows"][0]["amount"],
                        Decimal("120000"),
                    )
                    self.assertContains(response, 'class="employee-workspace-shell is-report-workspace"')
                    self.assertContains(response, "Doanh thu hàng hóa theo ngày")
                    self.assertContains(response, "Theo khu vực giao")
                    self.assertContains(response, "Xuất Excel")

    def test_staff_can_view_stock_and_request_restock_after_customer_shortage(self):
        dry_product = Product.objects.create(
            sku="FM-STAFF-STOCK-001",
            slug="staff-stock-item",
            name="Thanh protein",
            category=Product.Category.DRY_GOODS,
            description="Đồ khô",
            price=Decimal("50000"),
            stock_quantity=0,
            shipping_weight_grams=200,
        )
        Product.objects.create(
            sku="FM-STAFF-FRESH-001",
            slug="staff-fresh-item",
            name="Salad tươi",
            category=Product.Category.SALAD,
            description="Món tươi",
            price=Decimal("60000"),
        )
        backorder = self.create_order(
            status=Order.Status.PENDING,
            total=Decimal("400000"),
        )
        backorder_item = OrderItem.objects.create(
            order=backorder,
            product=dry_product,
            product_sku=dry_product.sku,
            product_name=dry_product.name,
            product_category=Product.Category.DRY_GOODS,
            unit_price=dry_product.price,
            quantity=8,
            line_total=Decimal("400000"),
        )
        restock_request = InventoryRestockRequest.objects.create(
            product=dry_product,
            product_name=dry_product.name,
            product_sku=dry_product.sku,
            requested_quantity=8,
            available_quantity=0,
        )
        employee = User.objects.create_user(
            username="inventory-sales-employee",
            email="inventory-sales@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(employee)

        menu_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "menu"},
        )

        self.assertContains(menu_response, "Kho còn 0")
        self.assertContains(menu_response, "Làm sau khi đặt")
        self.assertContains(menu_response, "Đơn chờ cần 8")

        self.client.post(
            reverse("staff_orders:update_status", args=[backorder.pk]),
            {"status": Order.Status.CONFIRMED},
        )
        backorder.refresh_from_db()
        self.assertEqual(backorder.status, Order.Status.CONFIRMED)
        self.client.post(
            reverse("staff_orders:update_status", args=[backorder.pk]),
            {"status": Order.Status.PACKING},
        )
        backorder.refresh_from_db()
        self.assertEqual(backorder.status, Order.Status.CONFIRMED)

        request_response = self.client.post(
            reverse(
                "staff_orders:request_inventory_restock",
                args=[dry_product.pk],
            )
        )
        self.assertRedirects(
            request_response,
            f"{reverse('staff_orders:dashboard')}?workspace=menu#staff-workspace",
        )
        restock_request.refresh_from_db()
        self.assertEqual(
            restock_request.status,
            InventoryRestockRequest.Status.MANAGER_REVIEW,
        )
        self.assertEqual(restock_request.requested_by, employee)

        forbidden_response = self.client.post(
            reverse(
                "staff_orders:fulfill_inventory_restock",
                args=[restock_request.pk],
            )
        )
        self.assertEqual(forbidden_response.status_code, 403)

        manager = User.objects.create_user(
            username="inventory-restock-manager",
            email="inventory-restock-manager@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)
        inventory_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "inventory"},
        )
        self.assertContains(inventory_response, "Yêu cầu bổ sung hàng")
        self.assertContains(inventory_response, "Thanh protein")

        insufficient_response = self.client.post(
            reverse(
                "staff_orders:fulfill_inventory_restock",
                args=[restock_request.pk],
            )
        )
        self.assertRedirects(
            insufficient_response,
            f"{reverse('staff_orders:dashboard')}?workspace=inventory#manager-inventory",
        )
        restock_request.refresh_from_db()
        self.assertEqual(
            restock_request.status,
            InventoryRestockRequest.Status.MANAGER_REVIEW,
        )

        self.client.post(
            f"{reverse('staff_orders:update_product', args=[dry_product.pk])}?workspace=inventory&product={dry_product.pk}",
            {"stock_quantity": "8", "low_stock_threshold": "5"},
        )
        fulfill_response = self.client.post(
            reverse(
                "staff_orders:fulfill_inventory_restock",
                args=[restock_request.pk],
            )
        )
        self.assertRedirects(
            fulfill_response,
            f"{reverse('staff_orders:dashboard')}?workspace=inventory#manager-inventory",
        )
        restock_request.refresh_from_db()
        self.assertEqual(restock_request.status, InventoryRestockRequest.Status.FULFILLED)
        self.assertEqual(restock_request.fulfilled_by, manager)
        backorder_item.refresh_from_db()
        dry_product.refresh_from_db()
        self.assertTrue(backorder_item.inventory_deducted)
        self.assertEqual(dry_product.stock_quantity, 0)

        self.client.force_login(employee)
        self.client.post(
            reverse("staff_orders:update_status", args=[backorder.pk]),
            {"status": Order.Status.PACKING},
        )
        backorder.refresh_from_db()
        self.assertEqual(backorder.status, Order.Status.PACKING)

    def test_manager_report_filters_custom_period_and_exports_summary_csv(self):
        recent_order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("90000.00"),
        )
        old_order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("60000.00"),
        )
        old_order.created_at = timezone.now() - timedelta(days=10)
        old_order.save(update_fields=["created_at"])
        manager = User.objects.create_user(
            username="report-workspace-manager",
            email="report-workspace-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)
        dashboard_url = reverse("staff_orders:dashboard")

        recent_response = self.client.get(
            dashboard_url,
            {"workspace": "reports", "range": "7d"},
        )
        self.assertEqual(
            recent_response.context["report_revenue"],
            recent_order.subtotal,
        )

        custom_start = (timezone.localdate() - timedelta(days=14)).isoformat()
        custom_end = timezone.localdate().isoformat()
        custom_response = self.client.get(
            dashboard_url,
            {
                "workspace": "reports",
                "range": "custom",
                "start": custom_start,
                "end": custom_end,
            },
        )
        self.assertEqual(
            custom_response.context["report_revenue"],
            recent_order.subtotal + old_order.subtotal,
        )
        self.assertEqual(custom_response.context["report_period_days"], 15)

        export_response = self.client.get(
            dashboard_url,
            {
                "workspace": "reports",
                "range": "custom",
                "start": custom_start,
                "end": custom_end,
                "export": "csv",
            },
        )
        self.assertEqual(export_response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Doanh thu hàng hóa", export_response.content.decode("utf-8-sig"))

    def test_manager_report_chart_scales_each_day_against_daily_peak(self):
        yesterday_order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("50000.00"),
        )
        yesterday_order.created_at = timezone.now() - timedelta(days=1)
        yesterday_order.save(update_fields=["created_at"])
        today_order = self.create_order(
            status=Order.Status.DELIVERED,
            total=Decimal("100000.00"),
        )
        today_order.created_at = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(10)),
            timezone.get_current_timezone(),
        )
        today_order.save(update_fields=["created_at"])
        processing_order = self.create_order(
            status=Order.Status.PREPARING,
            total=Decimal("25000.00"),
        )
        processing_order.created_at = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(8)),
            timezone.get_current_timezone(),
        )
        processing_order.save(update_fields=["created_at"])
        manager = User.objects.create_user(
            username="report-chart-manager",
            email="report-chart-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "reports", "range": "7d"},
        )

        points_by_day = {
            point["day"]: point for point in response.context["report_chart_points"]
        }
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        self.assertEqual(points_by_day[yesterday]["amount"], Decimal("50000.00"))
        self.assertEqual(points_by_day[today]["amount"], Decimal("100000.00"))
        self.assertEqual(points_by_day[yesterday]["height"], 50.0)
        self.assertEqual(points_by_day[today]["height"], 100.0)
        self.assertEqual(points_by_day[yesterday]["height_px"], 80)
        self.assertEqual(points_by_day[today]["height_px"], 160)
        self.assertContains(response, 'style="height:80px"')
        self.assertContains(response, 'style="height:160px"')
        self.assertNotContains(response, 'class="manager-report-chart-axis"')
        self.assertGreater(
            points_by_day[today]["height"],
            points_by_day[yesterday]["height"],
        )

        today_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "reports", "range": "today"},
        )
        today_points = today_response.context["report_chart_points"]
        self.assertEqual(
            [point["label"] for point in today_points],
            ["6–9h", "9–12h", "12–15h", "15–18h", "18–21h"],
        )
        self.assertEqual(today_points[0]["amount"], Decimal("25000.00"))
        self.assertEqual(today_points[1]["amount"], Decimal("100000.00"))
        self.assertContains(
            today_response,
            "Doanh thu đặt hàng theo khung giờ hôm nay",
        )

        outside_order = self.create_order(
            status=Order.Status.PENDING,
            total=Decimal("10000.00"),
        )
        outside_order.created_at = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(23)),
            timezone.get_current_timezone(),
        )
        outside_order.save(update_fields=["created_at"])
        outside_hours_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "reports", "range": "today"},
        )
        outside_hours_points = outside_hours_response.context["report_chart_points"]
        self.assertEqual(outside_hours_points[-1]["label"], "Ngoài giờ")
        self.assertEqual(
            outside_hours_points[-1]["amount"],
            Decimal("10000.00"),
        )

    def test_manager_can_manage_products_and_price_inventory_changes_are_logged(self):
        manager = User.objects.create_user(
            username="catalog-manager",
            email="catalog-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)
        product_data = {
            "sku": "FM-MANAGER-001",
            "slug": "manager-salad",
            "name": "Salad quản lý",
            "category": Product.Category.SALAD,
            "description": "Món salad giàu dinh dưỡng",
            "price": "129000",
            "stock_quantity": "12",
            "low_stock_threshold": "5",
            "is_available": "on",
            "calories": "410",
            "protein": "30",
            "carbs": "20",
            "fat": "15",
        }

        response = self.client.post(
            reverse("staff_orders:create_product"),
            product_data,
        )

        product = Product.objects.get(sku="FM-MANAGER-001")
        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?workspace=menu&product={product.pk}#manager-products",
        )
        self.assertIsNone(product.stock_quantity)
        inventory_product = Product.objects.create(
            sku="FM-MANAGER-DRY-001",
            slug="manager-dry-goods",
            name="Granola quản lý",
            category=Product.Category.DRY_GOODS,
            description="Đồ khô đóng gói",
            price=Decimal("99000"),
            stock_quantity=12,
            shipping_weight_grams=500,
        )
        self.assertTrue(
            ProductActivity.objects.filter(
                product=product,
                action=ProductActivity.Action.CREATED,
                actor=manager,
            ).exists()
        )
        inventory_page = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "inventory", "product": inventory_product.pk},
        )
        self.assertEqual(
            set(inventory_page.context["selected_product_form"].fields),
            {"stock_quantity", "low_stock_threshold", "shipping_weight_grams", "expiry_date"},
        )
        self.assertContains(inventory_page, "Tồn kho")
        self.assertNotContains(inventory_page, "Tồn kho (đơn vị)")
        self.assertNotContains(inventory_page, "12 đơn vị")
        self.assertNotContains(inventory_page, "Salad quản lý")
        response = self.client.post(
            f"{reverse('staff_orders:update_product', args=[product.pk])}?workspace=menu&product={product.pk}",
            {
                "price": "139000",
                "stock_quantity": "12",
                "low_stock_threshold": "5",
                "calories": "420",
                "is_available": "on",
            },
        )

        product.refresh_from_db()
        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?workspace=menu&product={product.pk}#manager-products",
        )
        self.assertEqual(product.price, Decimal("139000"))
        self.assertIsNone(product.stock_quantity)
        price_activity = ProductActivity.objects.filter(
            product=product,
            action=ProductActivity.Action.PRICE_CHANGED,
            actor=manager,
        )
        self.assertTrue(
            price_activity.filter(
                old_value="129000.00",
                new_value="139000.00",
            ).exists(),
            list(price_activity.values("old_value", "new_value")),
        )

        response = self.client.post(
            f"{reverse('staff_orders:update_product', args=[inventory_product.pk])}?workspace=inventory&product={inventory_product.pk}",
            {"stock_quantity": "2", "low_stock_threshold": "5"},
        )
        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?workspace=inventory&product={inventory_product.pk}#manager-inventory",
        )
        inventory_product.refresh_from_db()
        self.assertEqual(
            inventory_product.stock_quantity,
            2,
            list(response.wsgi_request._messages),
        )
        self.assertTrue(
            ProductActivity.objects.filter(
                product=inventory_product,
                action=ProductActivity.Action.INVENTORY_CHANGED,
                actor=manager,
            ).exists()
        )

        page = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "menu", "product": product.pk},
        )
        self.assertContains(page, "Lịch sử giá")
        self.assertContains(page, "129000₫ → 139000₫")
        self.assertContains(page, "Làm sau khi đặt")
        self.assertNotIn("stock_quantity", page.context["selected_product_form"].fields)

    def test_manager_product_create_page_saves_draft_with_generated_identifiers(self):
        manager = User.objects.create_user(
            username="catalog-page-manager",
            email="catalog-page-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        response = self.client.get(reverse("staff_orders:create_product"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "XEM TRƯỚC TRÊN TRANG KHÁCH")
        self.assertContains(response, "Đủ điều kiện mở bán")

        response = self.client.post(
            reverse("staff_orders:create_product"),
            {
                "name": "Salad nháp",
                "category": Product.Category.SALAD,
                "description": "Món salad đang hoàn thiện",
                "price": "79000",
                "calories": "320",
                "protein": "28",
                "carbs": "24",
                "fat": "9",
                "save_mode": "draft",
            },
        )

        product = Product.objects.get(name="Salad nháp")
        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?workspace=menu&product={product.pk}#manager-products",
        )
        self.assertFalse(product.is_available)
        self.assertTrue(product.sku.startswith("FM-"))
        self.assertTrue(product.slug.startswith("salad-nhap-"))

    def test_product_create_page_rejects_incomplete_product_for_publish(self):
        manager = User.objects.create_user(
            username="catalog-publish-manager",
            email="catalog-publish-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)

        response = self.client.post(
            reverse("staff_orders:create_product"),
            {
                "name": "Salad chưa đủ",
                "category": Product.Category.SALAD,
                "description": "Món chưa đủ dữ liệu",
                "price": "79000",
                "calories": "320",
                "protein": "28",
                "carbs": "24",
                "fat": "9",
                "save_mode": "publish",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Cần điền thông tin này để mở bán món.", status_code=400)
        self.assertFalse(Product.objects.filter(name="Salad chưa đủ").exists())

    def test_sales_employee_cannot_manage_products_or_access_manager_reports(self):
        product = Product.objects.create(
            sku="FM-SALES-001",
            slug="sales-product",
            name="Món chỉ bán",
            category=Product.Category.MEAL,
            description="Mô tả",
            price=Decimal("50000"),
            stock_quantity=7,
        )
        employee = User.objects.create_user(
            username="catalog-sales",
            email="catalog-sales@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(employee)

        response = self.client.post(
            reverse("staff_orders:update_product", args=[product.pk]),
            {
                "price": "1000",
                "stock_quantity": "0",
                "low_stock_threshold": "5",
                "calories": "0",
                "is_available": "on",
            },
        )
        self.assertEqual(response.status_code, 403)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("50000"))
        self.assertIsNone(product.stock_quantity)

        response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "reports"},
        )
        self.assertEqual(response.context["active_workspace"], "work")
        self.assertNotContains(response, "Báo cáo doanh thu")

    def test_sales_employee_can_pause_and_restore_product_availability(self):
        product = Product.objects.create(
            sku="FM-SALES-AVAIL-001",
            slug="sales-availability-product",
            name="Banana Whey",
            category=Product.Category.DRINK,
            description="Mô tả",
            price=Decimal("59000"),
            stock_quantity=8,
        )
        employee = User.objects.create_user(
            username="availability-sales",
            email="availability-sales@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(employee)

        menu_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "menu"},
        )
        self.assertContains(menu_response, "Banana Whey")
        self.assertContains(menu_response, "Đang bán")
        self.assertContains(
            menu_response,
            'type="checkbox" name="is_available" value="true" checked',
        )

        toggle_url = reverse("staff_orders:toggle_product_availability", args=[product.pk])
        pause_response = self.client.post(
            f"{toggle_url}?workspace=menu&filter=fresh&q=Banana",
            {"is_available": "false"},
        )

        self.assertRedirects(
            pause_response,
            f"{reverse('staff_orders:dashboard')}?workspace=menu&filter=fresh&q=Banana#staff-workspace",
        )
        product.refresh_from_db()
        self.assertFalse(product.is_available)
        self.assertEqual(product.price, Decimal("59000"))
        self.assertIsNone(product.stock_quantity)
        self.assertTrue(
            ProductActivity.objects.filter(
                product=product,
                actor=employee,
                action=ProductActivity.Action.AVAILABILITY_CHANGED,
                old_value="Đang bán",
                new_value="Tạm ngưng",
            ).exists()
        )
        invalid_response = self.client.post(toggle_url, {"is_available": "on"})
        self.assertRedirects(
            invalid_response,
            f"{reverse('staff_orders:dashboard')}?workspace=menu&filter=all&q=#staff-workspace",
        )
        product.refresh_from_db()
        self.assertFalse(product.is_available)
        self.assertEqual(
            ProductActivity.objects.filter(
                product=product,
                action=ProductActivity.Action.AVAILABILITY_CHANGED,
            ).count(),
            1,
        )

        paused_menu_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "menu"},
        )
        self.assertContains(paused_menu_response, "Banana Whey")
        self.assertContains(paused_menu_response, "Tạm hết hàng")
        self.assertContains(paused_menu_response, 'aria-label="Mở bán lại Banana Whey"')
        restore_response = self.client.post(
            toggle_url,
            {"is_available": ["false", "true"]},
        )

        self.assertRedirects(
            restore_response,
            f"{reverse('staff_orders:dashboard')}?workspace=menu&filter=all&q=#staff-workspace",
        )
        product.refresh_from_db()
        self.assertTrue(product.is_available)
        self.assertEqual(
            ProductActivity.objects.filter(
                product=product,
                actor=employee,
                action=ProductActivity.Action.AVAILABILITY_CHANGED,
            ).count(),
            2,
        )

    def test_employee_menu_shows_simple_dry_stock_and_filters_products(self):
        dry_product = Product.objects.create(
            sku="FM-STAFF-MENU-DRY",
            slug="staff-menu-dry",
            name="Hạt điều rang",
            category=Product.Category.DRY_GOODS,
            description="Đồ khô",
            price=Decimal("89000"),
            stock_quantity=12,
            shipping_weight_grams=500,
            serving="Túi 1kg",
        )
        fresh_product = Product.objects.create(
            sku="FM-STAFF-MENU-FRESH",
            slug="staff-menu-fresh",
            name="Salad gà",
            category=Product.Category.SALAD,
            description="Món tươi",
            price=Decimal("69000"),
            serving="1 phần",
        )
        employee = User.objects.create_user(
            username="staff-menu-inventory",
            email="staff-menu-inventory@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(employee)

        menu_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "menu"},
        )

        self.assertContains(menu_response, "Kho còn 12")
        self.assertContains(menu_response, "Làm sau khi đặt")
        self.assertNotContains(menu_response, dry_product.serving)
        self.assertNotContains(menu_response, fresh_product.serving)

        dry_filter_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "menu", "filter": "dry"},
        )
        self.assertContains(dry_filter_response, dry_product.name)
        self.assertNotContains(dry_filter_response, fresh_product.name)

        fresh_filter_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "menu", "filter": "fresh"},
        )
        self.assertContains(fresh_filter_response, fresh_product.name)
        self.assertNotContains(fresh_filter_response, dry_product.name)

    def test_customer_cannot_toggle_product_availability(self):
        product = Product.objects.create(
            sku="FM-CUSTOMER-AVAIL-001",
            slug="customer-availability-product",
            name="Món hạn chế",
            category=Product.Category.MEAL,
            description="Mô tả",
            price=Decimal("50000"),
        )
        customer = User.objects.create_user(
            username="availability-customer",
            email="availability-customer@example.com",
            password="Customer-Strong-2026!",
        )
        self.client.force_login(customer)

        response = self.client.post(
            reverse("staff_orders:toggle_product_availability", args=[product.pk]),
            {"is_available": "false"},
        )

        self.assertEqual(response.status_code, 403)


    def test_staff_can_create_and_quick_edit_real_products(self):
        admin_user = User.objects.create_superuser(
            username="product-admin",
            email="product-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        product_data = {
            "sku": "FM-STAFF-001",
            "slug": "staff-whey",
            "name": "Whey quản trị",
            "category": Product.Category.DRINK,
            "description": "Thức uống bổ sung protein",
            "price": "120000.00",
            "is_available": "on",
            "calories": "250",
            "protein": "25.5",
            "carbs": "12",
            "fat": "4",
        }
        form = ProductCreateForm(data=product_data)
        self.assertTrue(form.is_valid(), form.errors)
        response = self.client.post(reverse("staff_orders:create_product"), product_data)
        self.assertRedirects(response, f"{reverse('staff_orders:dashboard')}?section=products#products")
        product = Product.objects.get(sku="FM-STAFF-001")
        self.assertTrue(product.is_available)

        response = self.client.post(
            reverse("staff_orders:update_product", args=[product.pk]),
            {"price": "135000.00", "is_featured": "on"},
        )
        self.assertRedirects(response, f"{reverse('staff_orders:dashboard')}?section=products&page=1#products")
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("135000.00"))
        self.assertFalse(product.is_available)
        self.assertTrue(product.is_featured)

    def test_staff_dashboard_has_live_product_customer_payment_and_shipping_sections(self):
        admin_user = User.objects.create_superuser(
            username="sections-admin",
            email="sections-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        for section, expected_text in (
            ("products", "Quản lý món ăn"),
            ("customers", "Khách hàng đã đăng ký"),
            ("payments", "Tổng hợp thanh toán"),
            ("shipping", "Theo dõi đơn đang xử lý"),
            ("security", "Lịch sử đăng nhập"),
            ("operations", "Tình trạng dịch vụ"),
        ):
            with self.subTest(section=section):
                response = self.client.get(reverse("staff_orders:dashboard"), {"section": section})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_text)


class OrderCarePrivacyTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="care-customer",
            email="care-customer@example.com",
            password="Customer-Strong-2026!",
        )
        self.manager = User.objects.create_user(
            username="care-manager",
            email="care-manager@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )

    def create_delivered_order(self, *, received_days_ago):
        return Order.objects.create(
            customer=self.customer,
            customer_name="Nguyen Van A",
            customer_email=self.customer.email,
            customer_phone="0901234567",
            address="12 Duong X",
            district="Quan 1",
            city="TP Ho Chi Minh",
            delivery_region=Order.DeliveryRegion.HO_CHI_MINH_CITY,
            delivery_date=timezone.localdate() - timedelta(days=received_days_ago),
            delivery_slot=Order.DeliverySlot.MORNING,
            status=Order.Status.DELIVERED,
            delivery_confirmed_at=timezone.now() - timedelta(days=received_days_ago),
            subtotal=Decimal("120000.00"),
            shipping_fee=Decimal("0.00"),
            total=Decimal("120000.00"),
        )

    def test_customer_can_submit_care_request_only_within_seven_days(self):
        order = self.create_delivered_order(received_days_ago=6)
        self.client.force_login(self.customer)
        endpoint = reverse("orders:customer_care_request", args=[order.pk])

        response = self.client.post(
            endpoint,
            {"request_type": OrderCareRequest.RequestType.RETURN, "details": "Sản phẩm bị hư hỏng"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            OrderCareRequest.objects.filter(
                order=order,
                request_type=OrderCareRequest.RequestType.RETURN,
                status=OrderCareRequest.Status.PENDING,
            ).exists()
        )

        order.delivery_confirmed_at = timezone.now() - timedelta(days=8)
        order.save(update_fields=["delivery_confirmed_at"])
        rejected_response = self.client.post(
            endpoint,
            {"request_type": OrderCareRequest.RequestType.COMPLAINT, "details": "Đã quá hạn"},
        )

        self.assertEqual(rejected_response.status_code, 302)
        self.assertFalse(
            OrderCareRequest.objects.filter(
                order=order,
                request_type=OrderCareRequest.RequestType.COMPLAINT,
            ).exists()
        )

    def test_rejected_return_request_blocks_all_future_care_requests(self):
        order = self.create_delivered_order(received_days_ago=2)
        care_request = OrderCareRequest.objects.create(
            order=order,
            request_type=OrderCareRequest.RequestType.RETURN,
            details="Sản phẩm bị hư hỏng",
            requested_by=self.customer,
        )
        resolve_url = reverse(
            "staff_orders:resolve_customer_care_request",
            args=[care_request.pk],
        )
        self.client.force_login(self.manager)
        resolution_response = self.client.post(
            resolve_url,
            {"decision": "reject", "resolution_note": "Không đủ điều kiện đổi trả."},
        )

        self.assertEqual(resolution_response.status_code, 302)
        care_request.refresh_from_db()
        self.assertEqual(care_request.status, OrderCareRequest.Status.REJECTED)

        self.client.force_login(self.customer)
        history_response = self.client.get(
            reverse("core:account"),
            {"tab": "orders"},
        )
        self.assertContains(
            history_response,
            "Đơn này không thể gửi thêm khiếu nại hoặc yêu cầu đổi/trả.",
        )
        self.assertNotContains(history_response, "Gửi khiếu nại")
        self.assertNotContains(history_response, "Gửi yêu cầu đổi/trả")

        endpoint = reverse("orders:customer_care_request", args=[order.pk])
        for request_type in (
            OrderCareRequest.RequestType.COMPLAINT,
            OrderCareRequest.RequestType.RETURN,
        ):
            with self.subTest(request_type=request_type):
                response = self.client.post(
                    endpoint,
                    {"request_type": request_type, "details": "Gửi lại yêu cầu"},
                )
                self.assertEqual(response.status_code, 302)

        self.assertEqual(OrderCareRequest.objects.filter(order=order).count(), 1)

    def test_pii_access_window_uses_the_supplied_time(self):
        order = self.create_delivered_order(received_days_ago=6)

        self.assertFalse(order.can_request_pii_access(timezone.now()))
        self.assertTrue(
            order.can_request_pii_access(timezone.now() + timedelta(days=2))
        )

    def test_manager_pii_access_after_seven_days_is_reasoned_and_audited(self):
        order = self.create_delivered_order(received_days_ago=8)
        care_request = OrderCareRequest.objects.create(
            order=order,
            request_type=OrderCareRequest.RequestType.COMPLAINT,
            details="Sản phẩm bị hư hỏng",
            requested_by=self.customer,
        )
        self.client.force_login(self.manager)

        queue_response = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "orders", "view": "customer_care"},
        )

        self.assertContains(queue_response, care_request.details)
        self.assertContains(queue_response, "Nhập lý do để mở thông tin có ghi nhật ký")
        self.assertNotContains(queue_response, "0901234567")

        pii_url = reverse("staff_orders:access_order_pii", args=[order.pk])
        form_response = self.client.get(pii_url)
        self.assertEqual(form_response.status_code, 200)
        self.assertIn("no-store", form_response["Cache-Control"])

        access_response = self.client.post(
            pii_url,
            {"reason": "Xác minh yêu cầu khiếu nại"},
        )

        self.assertEqual(access_response.status_code, 200)
        self.assertIn("no-store", access_response["Cache-Control"])
        self.assertContains(access_response, "0901234567")
        self.assertEqual(OrderPiiAccessLog.objects.filter(order=order).count(), 1)

        sales_employee = User.objects.create_user(
            username="care-sales",
            email="care-sales@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(sales_employee)
        self.assertEqual(self.client.get(pii_url).status_code, 403)

    def test_expired_pii_purge_keeps_area_but_removes_identifiers_and_request_text(self):
        order = self.create_delivered_order(received_days_ago=366)
        another_order = self.create_delivered_order(received_days_ago=367)
        original_tracking_token = order.tracking_token
        care_request = OrderCareRequest.objects.create(
            order=order,
            request_type=OrderCareRequest.RequestType.RETURN,
            details="Địa chỉ 12 Duong X và số 0901234567",
            requested_by=self.customer,
        )

        purged_count = purge_expired_order_pii()

        self.assertEqual(purged_count, 2)
        order.refresh_from_db()
        another_order.refresh_from_db()
        care_request.refresh_from_db()
        self.assertIsNone(order.customer_id)
        self.assertIsNone(another_order.customer_id)
        self.assertNotEqual(order.tracking_token, original_tracking_token)
        self.assertNotEqual(order.tracking_token, another_order.tracking_token)
        self.assertEqual(order.customer_name, "")
        self.assertEqual(order.customer_email, "")
        self.assertEqual(order.customer_phone, "")
        self.assertEqual(order.address, "")
        self.assertEqual(order.district, "Quan 1")
        self.assertEqual(order.city, "TP Ho Chi Minh")
        self.assertEqual(order.customer_pii_encrypted, "")
        self.assertIsNotNone(order.customer_pii_purged_at)
        self.assertEqual(care_request.details, "")
        self.assertIsNone(care_request.requested_by_id)

    def test_migration_restores_locality_from_existing_encrypted_snapshots(self):
        order = self.create_delivered_order(received_days_ago=1)
        Order.objects.filter(pk=order.pk).update(district="", city="")
        migration = import_module(
            "apps.orders.migrations.0015_order_customer_pii_purged_at_ordercarerequest_and_more"
        )

        migration.restore_order_regions(apps, SimpleNamespace(connection=connection))

        order.refresh_from_db()
        self.assertEqual(order.district, "Quan 1")
        self.assertEqual(order.city, "TP Ho Chi Minh")
