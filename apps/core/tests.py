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
