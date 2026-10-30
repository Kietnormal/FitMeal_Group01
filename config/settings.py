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

# Mặc định dùng SQLite cho dễ chạy. Server thật đặt DATABASE_URL trỏ tới PostgreSQL.
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}

# Model người dùng tùy biến: PHẢI khai báo trước lần migrate đầu tiên
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "admin:login"  # tạm thời; đổi khi làm xong trang đăng nhập khách hàng

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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Bảo mật khi chạy thật (DEBUG=False). Mỗi mục bật/tắt được bằng .env.
if not DEBUG:
    SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
    CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    if env.bool("USE_PROXY_SSL_HEADER", default=False):
        # Bật khi chạy sau Nginx/reverse proxy đã xử lý HTTPS
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
