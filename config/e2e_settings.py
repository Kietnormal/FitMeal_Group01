import os

os.environ["SECRET_KEY"] = "dev-only-playwright-test-key"
os.environ["DEBUG"] = "True"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from .settings import *

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / ".playwright-e2e.sqlite3",
    }
}
MOMO_ENABLED = False
BANK_TRANSFER_ENABLED = False
VNPAY_ENABLED = False
# E-mails (e.g. password reset codes) are written to files so Playwright tests can read them.
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = BASE_DIR / ".playwright-emails"
