import base64
import hashlib
from tempfile import TemporaryDirectory

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.operations import create_database_backup, get_database_backup
from apps.products.models import Product

class CoreViewsTests(TestCase):
    def test_home_page_ok(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FitMeal")
        self.assertNotContains(response, "Theo dõi đơn")

    def test_home_featured_products_come_from_database(self):
        Product.objects.create(
            sku="FM-HOME-001",
            slug="featured-unavailable",
            name="Món nổi bật trong database",
            category=Product.Category.MEAL,
            description="Đang tạm hết",
            price="50000",
            is_available=False,
            is_featured=True,
        )
        Product.objects.create(
            sku="FM-HOME-002",
            slug="not-featured",
            name="Món không nổi bật",
            category=Product.Category.MEAL,
            description="Không hiển thị trên trang chủ",
            price="60000",
        )

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "Món nổi bật trong database")
        self.assertContains(response, "TẠM HẾT MÓN")
        self.assertNotContains(response, "Món không nổi bật")
        self.assertNotContains(response, "Banana Whey")

    def test_shop_page_does_not_render_static_demo_products(self):
        response = self.client.get(reverse("core:shop"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-product-grid")
        self.assertContains(response, "storefront.js?v=20261117-momo-bank-payments-1")
        self.assertContains(response, "storefront.css?v=20261117-payments-1")
        self.assertNotContains(response, "Banana Whey")
        self.assertNotContains(response, "Granola Crunch")

    def test_authenticated_user_remains_signed_in_on_home_page(self):
        user = get_user_model().objects.create_user(
            username="google-customer",
            email="google-customer@example.com",
            first_name="Google Customer",
        )
        self.client.force_login(user, backend="allauth.account.auth_backends.AuthenticationBackend")

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Xin chào, Google Customer")
        self.assertNotContains(response, ">Đăng nhập</a>")
        self.assertNotContains(response, ">Đăng ký</a>")

    def test_staff_navigation_links_to_order_management(self):
        user = get_user_model().objects.create_superuser(
            username="store-admin",
            email="store-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:cart"))

        self.assertContains(response, reverse("staff_orders:dashboard"))
        self.assertContains(response, "Quản trị đơn hàng")
        self.assertContains(response, "Quản trị demo")

    def test_cart_does_not_duplicate_order_history(self):
        response = self.client.get(reverse("core:cart"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "data-cart-order-history")
        self.assertNotContains(response, "data-cart-order-list")
        self.assertNotContains(response, "Lịch sử đơn hàng")

    def test_tracking_page_uses_manual_lookup_without_order_history(self):
        response = self.client.get(reverse("core:tracking"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-tracking-form")
        self.assertContains(response, "Dán mã tra cứu đơn hàng")
        self.assertNotContains(response, "data-tracking-history")
        self.assertNotContains(response, "Lịch sử đơn hàng trên thiết bị")

    def test_shop_has_cart_drawer_linking_to_checkout(self):
        response = self.client.get(reverse("core:shop"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-cart-drawer-items')
        self.assertContains(response, 'data-cart-drawer-empty')
        self.assertContains(response, f'href="{reverse("core:checkout")}" data-checkout-link')

    def test_healthz_ok(self):
        response = self.client.get(reverse("core:healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_storefront_pages_render(self):
        page_names = [
            "shop",
            "cart",
            "checkout",
            "tracking",
            "account",
            "policies",
        ]

        for page_name in page_names:
            with self.subTest(page=page_name):
                response = self.client.get(reverse(f"core:{page_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "FITMEAL.VN")

    def test_policies_page_discloses_demo_status_and_support_sections(self):
        response = self.client.get(reverse("core:policies"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chính sách & hỗ trợ")
        self.assertContains(response, "Đổi trả & hoàn tiền")
        self.assertContains(response, "Quyền riêng tư")
        self.assertContains(response, "chỉ giao trong TP. Hồ Chí Minh")
        self.assertContains(response, "giao toàn quốc")
        self.assertContains(response, "1–5 ngày")
        self.assertContains(response, "Phí đồ khô")
        self.assertContains(response, 'href="mailto:hello@fitmeal.vn"')

    def test_storefront_footer_links_to_policies_and_support(self):
        response = self.client.get(reverse("core:shop"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nhận đơn 6:00 – 21:00 mỗi ngày")
        self.assertContains(response, 'data-close-announcement aria-label="Đóng thông báo"')
        self.assertContains(response, f'href="{reverse("core:policies")}#delivery">Xem khung giờ')
        self.assertContains(response, reverse("core:policies"))
        self.assertContains(response, 'href="mailto:hello@fitmeal.vn"')
        self.assertContains(response, 'data-catalog-status role="status"')
        self.assertContains(
            response,
            f'href="{reverse("staff_orders:dashboard")}">Quản trị demo ↗</a>',
        )

    def test_demo_admin_route_is_removed(self):
        response = self.client.get("/demo-admin/")
        self.assertEqual(response.status_code, 404)

    def test_checkout_offers_momo_bank_transfer_and_cod(self):
        response = self.client.get(reverse("core:checkout"))

        self.assertContains(response, 'name="payment" value="momo"')
        self.assertContains(response, 'name="payment" value="bank_transfer"')
        self.assertContains(response, 'name="payment" value="cod"')
        self.assertNotContains(response, 'name="payment" value="vnpay"')
        self.assertNotContains(response, "VNPay")
        self.assertNotContains(response, 'class="solid-button submit-order" type="submit" disabled')

    def test_customer_demo_has_shopping_account_and_order_controls(self):
        pages = {
            "shop": ("data-price-min", "data-calorie-filter", "data-product-modal", "data-detail-ingredients", "data-detail-image"),
            "account": ("data-account-form=\"login\"", "data-account-form=\"register\"", "Đăng ký công khai chỉ tạo tài khoản khách hàng"),
            "checkout": ("name=\"address\"", "delivery-date", "name=\"accept_policy\"", "data-order-tracking-url", "data-checkout-success", "Bạn đã đặt đơn thành công!", "Xem đơn hàng của bạn tại đây", "data-checkout-error"),
            "tracking": ("data-tracking-form", "data-cancel-order", "data-tracking-timeline"),
        }

        for page_name, expected_content in pages.items():
            response = self.client.get(reverse(f"core:{page_name}"))
            with self.subTest(page=page_name):
                self.assertEqual(response.status_code, 200)
                for content in expected_content:
                    self.assertContains(response, content)

    def test_authenticated_checkout_links_to_the_customer_order_history(self):
        user = get_user_model().objects.create_user(
            username="checkout-order-history",
            email="checkout-order-history@example.com",
            password="Customer-Strong-2026!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("core:checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'data-order-history-url="{reverse("core:account")}?tab=orders#orders"',
        )


class DatabaseBackupTests(TestCase):
    def test_backup_is_encrypted_and_download_lookup_rejects_path_traversal(self):
        with TemporaryDirectory() as backup_root:
            with override_settings(
                BACKUP_ROOT=backup_root,
                BACKUP_ENCRYPTION_KEY="test-backup-encryption-key",
            ):
                backup = create_database_backup()
                key = base64.urlsafe_b64encode(
                    hashlib.sha256(b"test-backup-encryption-key").digest()
                )
                plaintext = Fernet(key).decrypt(backup.read_bytes()).decode("utf-8")

                self.assertTrue(plaintext.startswith("["))
                self.assertEqual(get_database_backup(backup.name), backup)
                self.assertIsNone(
                    get_database_backup(f"fitmeal-..\\..\\{backup.name}")
                )

    def test_mobile_storefront_filters_are_grouped_for_touch_layout(self):
        response = self.client.get(reverse("core:shop"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="catalog-category-filters"')
        self.assertContains(response, 'class="catalog-refinements"')
