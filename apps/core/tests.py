from django.test import TestCase
from django.urls import reverse


class CoreViewsTests(TestCase):
    def test_home_page_ok(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "FitMeal")

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
            "demo_admin",
        ]

        for page_name in page_names:
            with self.subTest(page=page_name):
                response = self.client.get(reverse(f"core:{page_name}"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "GIAO DIỆN MINH HỌA")

    def test_admin_demo_has_product_and_account_controls(self):
        response = self.client.get(reverse("core:demo_admin"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-product-form")
        self.assertContains(response, "data-admin-product-list")
        self.assertContains(response, "data-admin-account-form")
        self.assertContains(response, "Đăng ký admin demo")

    def test_customer_demo_has_shopping_account_and_order_controls(self):
        pages = {
            "shop": ("data-price-min", "data-calorie-filter", "data-product-modal", "data-detail-ingredients"),
            "account": ("data-account-form=\"reset\"", "data-account-profile", "data-profile-form", "data-account-orders"),
            "checkout": ("delivery-date", "data-payment-demo", "data-order-result-message", "data-fill-profile"),
            "tracking": ("data-tracking-history", "data-cancel-order", "data-tracking-timeline"),
        }

        for page_name, expected_content in pages.items():
            response = self.client.get(reverse(f"core:{page_name}"))
            with self.subTest(page=page_name):
                self.assertEqual(response.status_code, 200)
                for content in expected_content:
                    self.assertContains(response, content)
