"""
Cấu hình Django cho FitMeal.
Mọi giá trị thay đổi theo môi trường (máy dev / server thật) đều đọc từ file .env
hoặc biến môi trường, KHÔNG viết cứng vào code.
"""
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
# Đọc file .env nếu có. Biến môi trường thật (ví dụ do Docker truyền vào) được ưu tiên hơn.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Chặn việc chạy thật với khóa bí mật mẫu
if not DEBUG and SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured("Đang dùng SECRET_KEY mẫu khi DEBUG=False. Hãy đặt khóa riêng trong .env.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Các app của dự án
    "apps.core",
    "apps.accounts",
    "apps.products",
    "apps.cart",
    "apps.orders",
    "apps.payments",
    "apps.shipping",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
    "apps.accounts.middleware.StaffMfaEnforcementMiddleware",
    "apps.accounts.middleware.StaffSessionTimeoutMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# DATABASE_URL có thể trỏ tới MySQL, PostgreSQL hoặc SQLite cho kiểm thử cục bộ.
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
if DATABASES["default"]["ENGINE"] == "django.db.backends.mysql":
    DATABASES["default"].setdefault("OPTIONS", {})["charset"] = "utf8mb4"

# Model người dùng tùy biến: PHẢI khai báo trước lần migrate đầu tiên
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "core:account"
LOGIN_REDIRECT_URL = "core:home"
ACCOUNT_SIGNUP_REDIRECT_URL = "core:home"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
SOCIALACCOUNT_LOGIN_ON_GET = False
MFA_TOTP_ISSUER = "FitMeal"
MFA_RECOVERY_CODES_SHOW_ONCE = True
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "OAUTH_PKCE_ENABLED": True,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Keep production media disabled unless an isolated demo explicitly opts in.
SERVE_PRODUCT_MEDIA = env.bool("SERVE_PRODUCT_MEDIA", default=False)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="FitMeal <noreply@fitmeal.vn>")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

MOMO_PARTNER_CODE = env("MOMO_PARTNER_CODE", default="")
MOMO_ACCESS_KEY = env("MOMO_ACCESS_KEY", default="")
MOMO_SECRET_KEY = env("MOMO_SECRET_KEY", default="")
MOMO_CREATE_PAYMENT_URL = env(
    "MOMO_CREATE_PAYMENT_URL",
    default="https://test-payment.momo.vn/v2/gateway/api/create",
)
MOMO_PUBLIC_BASE_URL = env("MOMO_PUBLIC_BASE_URL", default="")
MOMO_ENABLED = bool(MOMO_PARTNER_CODE and MOMO_ACCESS_KEY and MOMO_SECRET_KEY)
BANK_TRANSFER_BANK_CODE = env("BANK_TRANSFER_BANK_CODE", default="")
BANK_TRANSFER_ACCOUNT_NUMBER = env("BANK_TRANSFER_ACCOUNT_NUMBER", default="")
BANK_TRANSFER_ACCOUNT_NAME = env("BANK_TRANSFER_ACCOUNT_NAME", default="")
SEPAY_API_KEY = env("SEPAY_API_KEY", default="")
BANK_TRANSFER_ENABLED = bool(
    BANK_TRANSFER_BANK_CODE
    and BANK_TRANSFER_ACCOUNT_NUMBER
    and BANK_TRANSFER_ACCOUNT_NAME
    and SEPAY_API_KEY
)
# Retained only to validate and display historical transactions.
VNPAY_TMN_CODE = env("VNPAY_TMN_CODE", default="")
VNPAY_HASH_SECRET = env("VNPAY_HASH_SECRET", default="")
VNPAY_PAYMENT_URL = env(
    "VNPAY_PAYMENT_URL",
    default="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
)
VNPAY_ENABLED = False
STAFF_SESSION_IDLE_TIMEOUT_SECONDS = env.int(
    "STAFF_SESSION_IDLE_TIMEOUT_SECONDS",
    default=30 * 60,
)
BACKUP_ROOT = Path(env("BACKUP_ROOT", default=str(BASE_DIR.parent / "fitmeal-backups")))
BACKUP_EXTERNAL_ROOT = env("BACKUP_EXTERNAL_ROOT", default="")
BACKUP_ENCRYPTION_KEY = env("BACKUP_ENCRYPTION_KEY", default="")
APP_VERSION = env("APP_VERSION", default="development")

# Bảo mật khi chạy thật (DEBUG=False). Mỗi mục bật/tắt được bằng .env.
if not DEBUG:
    SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
    CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
        "SECURE_HSTS_INCLUDE_SUBDOMAINS",
        default=False,
    )
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    if env.bool("USE_PROXY_SSL_HEADER", default=False):
        # Bật khi chạy sau Nginx/reverse proxy đã xử lý HTTPS
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
