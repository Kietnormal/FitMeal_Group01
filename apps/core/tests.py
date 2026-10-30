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
