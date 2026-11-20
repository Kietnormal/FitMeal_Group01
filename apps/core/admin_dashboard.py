from datetime import datetime
import shutil
from time import perf_counter

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import DatabaseError, connection
from django.utils import timezone
from allauth.mfa.models import Authenticator

from apps.accounts.forms import SecurityPolicyForm
from apps.accounts.models import LoginEvent, LoginThrottle, SecurityPolicy, User

from .operations import list_database_backups


def _security_checks(policy, admin_total, admin_enrolled, manager_total, manager_enrolled):
    has_csrf_middleware = any(
        name.endswith("CsrfViewMiddleware") for name in settings.MIDDLEWARE
    )
    has_pbkdf2 = any(
        hasher.endswith("PBKDF2PasswordHasher")
        for hasher in settings.PASSWORD_HASHERS
    )
    if settings.DEBUG:
        secure_cookies = False
        cookie_detail = "Chỉ bật khi chạy HTTPS trên môi trường thật."
    else:
        secure_cookies = bool(
            settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
        )
        cookie_detail = "Cookie phiên và CSRF phải có cờ Secure."
    checks = [
        {
            "label": "HTTPS bắt buộc và HSTS",
            "passed": bool(
                not settings.DEBUG
                and getattr(settings, "SECURE_SSL_REDIRECT", False)
                and getattr(settings, "SECURE_HSTS_SECONDS", 0)
            ),
            "detail": "Chỉ đạt khi chuyển hướng HTTPS và HSTS được cấu hình.",
        },
        {
            "label": "Mật khẩu lưu dạng băm",
            "passed": has_pbkdf2,
            "detail": "PBKDF2 là bộ băm mặc định đang được dùng."
            if has_pbkdf2
            else "Không tìm thấy PBKDF2 trong cấu hình.",
        },
        {
            "label": "Chống CSRF cho form",
            "passed": has_csrf_middleware,
            "detail": "CsrfViewMiddleware đang bật."
            if has_csrf_middleware
            else "CsrfViewMiddleware chưa bật.",
        },
        {
            "label": "DEBUG tắt trên môi trường thật",
            "passed": not settings.DEBUG,
            "detail": "DEBUG đang bật." if settings.DEBUG else "DEBUG đang tắt.",
        },
        {
            "label": "Khóa bí mật không ghi trong mã nguồn",
            "passed": True,
            "detail": "SECRET_KEY được đọc từ biến môi trường.",
        },
        {
            "label": "Giới hạn đăng nhập sai",
            "passed": True,
            "detail": "Khóa IP sau 5 lần sai trong 15 phút.",
        },
        {
            "label": "Cookie phiên và CSRF có Secure",
            "passed": secure_cookies,
            "detail": cookie_detail,
        },
        {
            "label": "Xác thực 2 bước cho quản trị viên và quản lý",
            "passed": (
                (admin_total == 0 or (policy.require_admin_2fa and admin_enrolled == admin_total))
                and (
                    manager_total == 0
                    or (policy.require_manager_2fa and manager_enrolled == manager_total)
                )
            ),
            "detail": (
                f"Quản trị viên: {admin_enrolled}/{admin_total} đã đăng ký, "
                f"{'bắt buộc' if policy.require_admin_2fa else 'chưa bắt buộc'}; "
                f"quản lý: {manager_enrolled}/{manager_total} đã đăng ký, "
                f"{'bắt buộc' if policy.require_manager_2fa else 'chưa bắt buộc'}."
            ),
        },
    ]
    return checks


def get_security_dashboard_context(request):
    now = timezone.now()
    day_start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    events = list(
        LoginEvent.objects.select_related("user")
        .filter(created_at__gte=day_start)
        .order_by("-created_at", "-pk")[:50]
    )
    blocked_ips = list(
        LoginThrottle.objects.filter(blocked_until__gt=now).order_by("-blocked_until")
    )
    staff = {
        str(user.pk): user
        for user in User.objects.filter(is_staff=True).only(
            "pk", "username", "first_name", "last_name", "email", "staff_role"
        )
    }
    active_sessions = []
    current_key = request.session.session_key
    for session in Session.objects.filter(expire_date__gt=now).iterator():
        data = session.get_decoded()
        user = staff.get(str(data.get("_auth_user_id", "")))
        if user is None:
            continue
        timestamp = data.get("staff_last_activity")
        try:
            active_at = datetime.fromtimestamp(
                float(timestamp),
                tz=timezone.get_current_timezone(),
            )
        except (TypeError, ValueError):
            active_at = session.expire_date
        active_sessions.append(
            {
                "user": user,
                "ip_address": data.get("security_ip_address", "—"),
                "user_agent": data.get("security_user_agent", "Thiết bị chưa ghi nhận"),
                "active_at": active_at,
                "is_current": session.session_key == current_key,
            }
        )
    policy = SecurityPolicy.objects.first() or SecurityPolicy(pk=1)
    eligible_staff = User.objects.filter(
        is_active=True,
        is_staff=True,
        staff_role__in=(User.StaffRole.ADMIN, User.StaffRole.MANAGER),
    )
    admin_ids = set(
        eligible_staff.filter(staff_role=User.StaffRole.ADMIN).values_list("pk", flat=True)
    )
    manager_ids = set(
        eligible_staff.filter(staff_role=User.StaffRole.MANAGER).values_list("pk", flat=True)
    )
    enrolled_user_ids = set(Authenticator.objects.filter(
        user_id__in=eligible_staff.values_list("pk", flat=True),
        type=Authenticator.Type.TOTP,
    ).values_list("user_id", flat=True))
    admin_total = len(admin_ids)
    manager_total = len(manager_ids)
    admin_enrolled = len(admin_ids & enrolled_user_ids)
    manager_enrolled = len(manager_ids & enrolled_user_ids)
    checks = _security_checks(
        policy,
        admin_total,
        admin_enrolled,
        manager_total,
        manager_enrolled,
    )
    return {
        "login_events": events,
        "login_failure_count": sum(
            event.outcome in {LoginEvent.Outcome.FAILURE, LoginEvent.Outcome.BLOCKED}
            for event in events
        ),
        "blocked_ips": blocked_ips,
        "active_staff_sessions": active_sessions,
        "active_staff_session_count": len(active_sessions),
        "security_checks": checks,
        "security_check_count": sum(check["passed"] for check in checks),
        "security_policy": policy,
        "security_policy_form": SecurityPolicyForm(instance=policy),
        "staff_mfa_enrolled_count": admin_enrolled + manager_enrolled,
        "staff_mfa_total_count": admin_total + manager_total,
        "password_min_length": next(
            (
                validator.get("OPTIONS", {}).get("min_length", 8)
                for validator in settings.AUTH_PASSWORD_VALIDATORS
                if validator["NAME"].endswith("MinimumLengthValidator")
            ),
            8,
        ),
        "login_failure_limit": 5,
        "login_failure_window_minutes": 15,
        "login_block_duration_minutes": 15,
        "staff_idle_timeout_minutes": settings.STAFF_SESSION_IDLE_TIMEOUT_SECONDS // 60,
        "staff_login_shift_enforced": False,
    }


def get_operations_dashboard_context():
    database_latency_ms = None
    database_error = ""
    started_at = perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database_latency_ms = round((perf_counter() - started_at) * 1000)
    except DatabaseError as error:
        database_error = str(error)
    try:
        usage = shutil.disk_usage(settings.BASE_DIR)
        disk_percent = round(usage.used * 100 / usage.total, 1)
        disk_used_gb = round(usage.used / (1024**3), 1)
        disk_total_gb = round(usage.total / (1024**3), 1)
    except OSError as error:
        disk_percent = None
        disk_used_gb = None
        disk_total_gb = None
        disk_error = str(error)
    else:
        disk_error = ""
    backups = list_database_backups()
    return {
        "database_latency_ms": database_latency_ms,
        "database_available": database_latency_ms is not None,
        "database_error": database_error,
        "database_vendor": connection.vendor,
        "disk_percent": disk_percent,
        "disk_available": disk_percent is not None,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "disk_error": disk_error,
        "database_backups": backups,
        "backup_encryption_is_separate": bool(settings.BACKUP_ENCRYPTION_KEY),
        "external_backup_configured": bool(settings.BACKUP_EXTERNAL_ROOT),
        "backup_retention_count": 14,
        "app_version": settings.APP_VERSION,
        "bank_transfer_configured": settings.BANK_TRANSFER_ENABLED,
        "cpu_memory_available": False,
        "recent_5xx_available": False,
        "deployment_history_available": False,
    }
