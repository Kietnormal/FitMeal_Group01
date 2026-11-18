import re
from datetime import date, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

from locust import HttpUser, between, task
from locust.exception import StopUser


CSRF_TOKEN_PATTERN = re.compile(
    r'name="csrfmiddlewaretoken"\s+value="([^"]+)"'
)
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
LOAD_TEST_PORT = 8766


class CheckoutUser(HttpUser):
    host = f"http://127.0.0.1:{LOAD_TEST_PORT}"
    wait_time = between(1, 2)

    def on_start(self):
        target = urlsplit(self.host)
        if (
            target.scheme != "http"
            or target.hostname not in LOCAL_HOSTS
            or target.port != LOAD_TEST_PORT
        ):
            self.environment.runner.quit()
            raise StopUser

        with self.client.get(
            "/api/products/",
            name="GET /api/products/",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Catalog returned HTTP {response.status_code}")
                raise StopUser
            response.success()

        with self.client.get(
            "/checkout/",
            name="GET /checkout/",
            catch_response=True,
        ) as response:
            token = CSRF_TOKEN_PATTERN.search(response.text)
            if response.status_code != 200 or token is None:
                response.failure("Checkout page or CSRF token unavailable")
                raise StopUser
            self.csrf_token = token.group(1)
            response.success()

        self.customer_id = uuid4().hex
        self.order_attempted = False

    @task
    def place_cod_order(self):
        if self.order_attempted:
            return
        self.order_attempted = True

        payload = {
            "name": f"Khach Locust {self.customer_id[:8]}",
            "email": f"locust-{self.customer_id}@example.test",
            "phone": f"09{int(self.customer_id[:8], 16) % 100_000_000:08d}",
            "address": "12 Duong Kiem Thu",
            "district": "Quan 1",
            "city": "TP Hồ Chí Minh",
            "delivery_date": (date.today() + timedelta(days=1)).isoformat(),
            "delivery_slot": "08:00–10:00",
            "note": "Locust local load test",
            "payment": "cod",
            "accept_policy": True,
            "items": [{"id": "playwright-whey", "quantity": 1}],
        }

        with self.client.post(
            "/api/orders/",
            json=payload,
            headers={"X-CSRFToken": self.csrf_token},
            name="POST /api/orders/ (COD)",
            catch_response=True,
        ) as response:
            try:
                result = response.json()
            except ValueError:
                response.failure(f"Order API returned HTTP {response.status_code} without JSON")
                return

            if response.status_code != 201 or not result.get("order_number"):
                response.failure(
                    f"Order API returned HTTP {response.status_code}: "
                    f"{result.get('error', 'order number missing')}"
                )
            else:
                response.success()
