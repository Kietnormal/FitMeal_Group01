from django.test import TestCase
from django.urls import reverse


class CoreViewsTests(TestCase):
    def test_home_page_ok(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FitMeal")
        self.assertNotContains(response, "Theo dõi đơn")

    def test_cart_has_order_tracking_prompt(self):
        response = self.client.get(reverse("core:cart"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-cart-order-history")
        self.assertContains(response, "data-cart-order-list")
        self.assertContains(response, "Nhấn vào đây để theo dõi đơn")

    def test_healthz_ok(self):
        response = self.client.get(reverse("core:healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_storefront_and_demo_pages_render(self):
        page_names = [
            "shop",
            "cart",
            "checkout",
            "tracking",
            "account",
            "policies",
            "demo_admin",
        ]

        for page_name in page_names:
            with self.subTest(page=page_name):
                response = self.client.get(reverse(f"core:{page_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "GIAO DIỆN MINH HỌA")

    def test_policies_page_discloses_demo_status_and_support_sections(self):
        response = self.client.get(reverse("core:policies"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chính sách & hỗ trợ")
        self.assertContains(response, "Đổi trả & hoàn tiền")
        self.assertContains(response, "Quyền riêng tư")
        self.assertContains(response, "chỉ phục vụ minh họa")
        self.assertContains(response, 'href="mailto:hello@fitmeal.vn"')

    def test_storefront_footer_links_to_policies_and_support(self):
        response = self.client.get(reverse("core:shop"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("core:policies"))
        self.assertContains(response, 'href="mailto:hello@fitmeal.vn"')

    def test_admin_demo_has_product_and_account_controls(self):
        response = self.client.get(reverse("core:demo_admin"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-product-form")
        self.assertContains(response, "data-admin-product-list")
        self.assertContains(response, "data-product-image")
        self.assertContains(response, "data-product-image-preview")
        self.assertContains(response, "data-admin-order-list")
        self.assertContains(response, "data-admin-recent-orders")
        self.assertContains(response, "data-admin-account-form")
        self.assertContains(response, "Đăng ký admin demo")

    def test_customer_demo_has_shopping_account_and_order_controls(self):
        pages = {
            "shop": ("data-price-min", "data-calorie-filter", "data-product-modal", "data-detail-ingredients", "data-detail-image"),
            "account": ("data-account-form=\"reset\"", "data-account-profile", "data-profile-form", "data-account-orders"),
            "checkout": ("delivery-date", "data-payment-demo", "data-order-result-message", "data-order-cart-link", "data-fill-profile"),
            "tracking": ("data-tracking-history", "data-cancel-order", "data-tracking-timeline"),
        }

        for page_name, expected_content in pages.items():
            response = self.client.get(reverse(f"core:{page_name}"))
            with self.subTest(page=page_name):
                self.assertEqual(response.status_code, 200)
                for content in expected_content:
                    self.assertContains(response, content)

    def test_mobile_storefront_filters_are_grouped_for_touch_layout(self):
        response = self.client.get(reverse("core:shop"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="catalog-category-filters"')
        self.assertContains(response, 'class="catalog-refinements"')
