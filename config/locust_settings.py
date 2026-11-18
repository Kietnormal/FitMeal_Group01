import os

from .e2e_settings import *

if os.environ.get("LOCUST_DATABASE_URL"):
    DATABASES = {"default": env.db("LOCUST_DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / ".locust-test.sqlite3",
            "OPTIONS": {
                "timeout": 30,
                "transaction_mode": "IMMEDIATE",
            },
        }
    }
