import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .settings import *


demo_dir_value = os.environ.get("MOMO_DEMO_DIR", "").strip()
demo_secret_key = os.environ.get("MOMO_DEMO_SECRET_KEY", "").strip()
demo_database_url = os.environ.get("MOMO_DEMO_DATABASE_URL", "").strip()
demo_hosts = os.environ.get("MOMO_DEMO_ALLOWED_HOSTS", "").strip()
demo_origins = os.environ.get("MOMO_DEMO_CSRF_TRUSTED_ORIGINS", "").strip()
public_base_url = os.environ.get("MOMO_DEMO_PUBLIC_BASE_URL", "").strip().rstrip("/")
demo_dir = Path(demo_dir_value).resolve() if demo_dir_value else None
allowed_hosts = [host.strip() for host in demo_hosts.split(",") if host.strip()]
trusted_origins = [origin.strip() for origin in demo_origins.split(",") if origin.strip()]

if not all(
    (
        demo_dir_value,
        demo_secret_key,
        demo_database_url,
        demo_hosts,
        demo_origins,
        public_base_url,
    )
):
    raise ImproperlyConfigured(
        "MOMO_DEMO_DIR, MOMO_DEMO_SECRET_KEY, MOMO_DEMO_DATABASE_URL, "
        "MOMO_DEMO_ALLOWED_HOSTS, MOMO_DEMO_CSRF_TRUSTED_ORIGINS, "
        "and MOMO_DEMO_PUBLIC_BASE_URL are required."
    )

if len(demo_secret_key) < 50 or demo_secret_key.startswith("dev-only"):
    raise ImproperlyConfigured("MOMO_DEMO_SECRET_KEY must be a unique random key.")

try:
    demo_database = env.db_url_config(demo_database_url)
except (TypeError, ValueError) as error:
    raise ImproperlyConfigured("MOMO_DEMO_DATABASE_URL is invalid.") from error

if demo_database["ENGINE"] != "django.db.backends.sqlite3":
    raise ImproperlyConfigured(
        "The MoMo demo must use its isolated SQLite database, not the application database."
    )

database_path = Path(demo_database["NAME"]).resolve()
if (
    demo_database["NAME"] == ":memory:"
    or demo_dir is None
    or demo_dir.is_relative_to(BASE_DIR.resolve())
    or not database_path.is_relative_to(demo_dir)
):
    raise ImproperlyConfigured(
        "The MoMo demo database must be a file inside a separate demo data directory."
    )

public_origin = urlsplit(public_base_url)
try:
    public_port = public_origin.port
except ValueError as error:
    raise ImproperlyConfigured(
        "MOMO_DEMO_PUBLIC_BASE_URL must be a real HTTPS origin without a path."
    ) from error

if (
    public_origin.scheme != "https"
    or not public_origin.hostname
    or public_origin.username
    or public_origin.password
    or public_port not in (None, 443)
    or public_origin.path
    or public_origin.query
    or public_origin.fragment
    or "<" in public_base_url
    or ">" in public_base_url
    or public_origin.hostname not in allowed_hosts
    or public_base_url not in trusted_origins
):
    raise ImproperlyConfigured(
        "The MoMo demo HTTPS origin must match its allowed host and CSRF trusted origin."
    )

if not MOMO_ENABLED:
    raise ImproperlyConfigured(
        "Set the MoMo sandbox credentials in the local environment before starting the demo."
    )

if urlsplit(MOMO_CREATE_PAYMENT_URL).hostname != "test-payment.momo.vn":
    raise ImproperlyConfigured(
        "The isolated demo only permits the MoMo sandbox endpoint."
    )

DEMO_DIR = Path(demo_dir_value).resolve()
SECRET_KEY = demo_secret_key
DEBUG = False
ALLOWED_HOSTS = allowed_hosts
CSRF_TRUSTED_ORIGINS = trusted_origins
DATABASES = {"default": demo_database}
STATIC_ROOT = DEMO_DIR / "staticfiles"
MEDIA_ROOT = DEMO_DIR / "media"
SERVE_PRODUCT_MEDIA = False
SERVE_DEMO_STATIC = True

MOMO_CREATE_PAYMENT_URL = "https://test-payment.momo.vn/v2/gateway/api/create"
MOMO_PUBLIC_BASE_URL = public_base_url
BANK_TRANSFER_BANK_CODE = ""
BANK_TRANSFER_ACCOUNT_NUMBER = ""
BANK_TRANSFER_ACCOUNT_NAME = ""
SEPAY_API_KEY = ""
BANK_TRANSFER_ENABLED = False
VNPAY_ENABLED = False
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
GOOGLE_OAUTH_CLIENT_ID = ""
GOOGLE_OAUTH_CLIENT_SECRET = ""
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_SSL_HOST = None
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
