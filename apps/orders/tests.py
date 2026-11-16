import json
from importlib import import_module
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib import admin
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PointsTransaction, User
from apps.products.forms import ProductCreateForm
from apps.products.models import Product, ProductActivity
from apps.payments.models import PaymentTransaction

from .admin import OrderAdmin
from .delivery import finalize_expired_delivery_confirmations
from .models import DeliveryIssue, Order, OrderCancellationRequest, OrderItem


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
            "payment": Order.PaymentMethod.COD,
            "accept_policy": True,
            "items": [{"id": self.product.slug, "quantity": 2}],
        }

    def post_order(self, payload=None):
        return self.client.post(
            reverse("orders:create"),
            data=json.dumps(payload if payload is not None else self.payload),
            content_type="application/json",
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
        self.assertEqual(order.subtotal, Decimal("200000.00"))
        self.assertEqual(order.shipping_fee, Decimal("20000.00"))
        self.assertEqual(order.total, Decimal("220000.00"))
        self.assertEqual(item.product_name, "Whey")
        self.assertEqual(item.unit_price, Decimal("100000.00"))
        self.assertEqual(item.quantity, 2)
        self.assertTrue(response.json()["tracking_token"])

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
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.post_order(payload)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_tracking_token_returns_order_status_without_customer_contact_data(self):
        create_response = self.post_order()
        token = create_response.json()["tracking_token"]

        response = self.client.get(reverse("orders:track", args=[token]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["order_number"], Order.objects.get().order_number)
        self.assertEqual(response.json()["status"], Order.Status.PENDING)
        self.assertNotIn("customer_email", response.json())
        self.assertNotIn("address", response.json())

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
        self.assertEqual(order.district, "")
        self.assertEqual(order.city, "")
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
        self.assertContains(response, "Đã mã hóa và ẩn sau khi đơn hoàn tất hoặc bị hủy.")
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
        self.assertContains(response, "Đã mã hóa và ẩn sau khi đơn hoàn tất hoặc bị hủy.")
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
        self.assertContains(response, "Giao dịch VNPay")

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
        for personal_data in ("Nguyen Van A", "customer@example.com", "0901234567", "12 Duong X"):
            with self.subTest(personal_data=personal_data):
                self.assertNotContains(response, personal_data)

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

        self.assertEqual(response.context["period_revenue"], Decimal("90000.00"))
        self.assertEqual(response.context["period_order_count"], 1)
        self.assertEqual(sum(point["amount"] for point in response.context["chart_points"]), Decimal("90000.00"))

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
            {"reason": "Khách xác nhận hủy đơn"},
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
        self.assertEqual(cancellation.status, OrderCancellationRequest.Status.APPROVED)
        self.assertTrue(order.customer_info_redacted)
        self.assertEqual(order.customer_phone, "")
        self.assertEqual(cancellation.reason, "")
        self.assertEqual(cancellation.manager_resolution_reason, "")

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
                        list(response.context["report_popular_products"])[0]["quantity"],
                        2,
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
        self.assertEqual(product.stock_quantity, 12)
        self.assertTrue(
            ProductActivity.objects.filter(
                product=product,
                action=ProductActivity.Action.CREATED,
                actor=manager,
            ).exists()
        )

        inventory_page = self.client.get(
            reverse("staff_orders:dashboard"),
            {"workspace": "inventory", "product": product.pk},
        )
        self.assertEqual(
            set(inventory_page.context["selected_product_form"].fields),
            {"stock_quantity", "low_stock_threshold", "shipping_weight_grams", "expiry_date"},
        )
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
        self.assertEqual(product.stock_quantity, 12)
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
            f"{reverse('staff_orders:update_product', args=[product.pk])}?workspace=inventory&product={product.pk}",
            {"stock_quantity": "2", "low_stock_threshold": "5"},
        )
        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?workspace=inventory&product={product.pk}#manager-inventory",
        )
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 2)
        self.assertTrue(
            ProductActivity.objects.filter(
                product=product,
                action=ProductActivity.Action.INVENTORY_CHANGED,
                actor=manager,
            ).exists()
        )

        page = self.client.get(reverse("staff_orders:dashboard"), {"workspace": "menu"})
        self.assertContains(page, "Lịch sử giá")
        self.assertContains(page, "129000₫ → 139000₫")

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
        self.assertEqual(product.stock_quantity, 7)

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
        self.assertContains(menu_response, "Tạm hết hàng")

        toggle_url = reverse("staff_orders:toggle_product_availability", args=[product.pk])
        pause_response = self.client.post(toggle_url, {"is_available": "false"})

        self.assertRedirects(
            pause_response,
            f"{reverse('staff_orders:dashboard')}?workspace=menu#staff-workspace",
        )
        product.refresh_from_db()
        self.assertFalse(product.is_available)
        self.assertEqual(product.price, Decimal("59000"))
        self.assertEqual(product.stock_quantity, 8)
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
            f"{reverse('staff_orders:dashboard')}?workspace=menu#staff-workspace",
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
        self.assertContains(paused_menu_response, "Mở bán lại")
        restore_response = self.client.post(toggle_url, {"is_available": "true"})

        self.assertRedirects(
            restore_response,
            f"{reverse('staff_orders:dashboard')}?workspace=menu#staff-workspace",
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
        product.refresh_from_db()
        self.assertTrue(product.is_available)

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
