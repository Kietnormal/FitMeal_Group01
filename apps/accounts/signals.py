from datetime import timedelta

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone
from allauth.mfa.models import Authenticator

from .models import LoginEvent, LoginThrottle

LOGIN_FAILURE_LIMIT = 5
LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
LOGIN_BLOCK_DURATION = timedelta(minutes=15)


def _request_data(request):
    if request is None:
        return "", ""
    return (
        request.META.get("REMOTE_ADDR", "")[:45],
        request.META.get("HTTP_USER_AGENT", "")[:255],
    )


@receiver(user_login_failed)
def record_failed_login(sender, credentials, request, **kwargs):
    identifier = str(credentials.get("username", credentials.get("login", "")))[:254]
    ip_address, user_agent = _request_data(request)
    now = timezone.now()
    if ip_address:
        with transaction.atomic():
            throttle, _ = LoginThrottle.objects.select_for_update().get_or_create(
                ip_address=ip_address
            )
            if throttle.window_started_at + LOGIN_FAILURE_WINDOW <= now:
                throttle.failure_count = 0
                throttle.window_started_at = now
                throttle.blocked_until = None
            throttle.failure_count += 1
            if throttle.failure_count >= LOGIN_FAILURE_LIMIT:
                throttle.blocked_until = now + LOGIN_BLOCK_DURATION
            throttle.save(
                update_fields=[
                    "failure_count",
                    "window_started_at",
                    "blocked_until",
                    "updated_at",
                ]
            )
    LoginEvent.objects.create(
        login_identifier=identifier,
        ip_address=ip_address,
        user_agent=user_agent,
        outcome=LoginEvent.Outcome.FAILURE,
        details="Sai mật khẩu hoặc tài khoản",
    )


@receiver(user_logged_in)
def record_successful_login(sender, request, user, **kwargs):
    ip_address, user_agent = _request_data(request)
    LoginEvent.objects.create(
        user=user,
        login_identifier=user.email or user.get_username(),
        ip_address=ip_address,
        user_agent=user_agent,
        outcome=LoginEvent.Outcome.SUCCESS,
        details="Đăng nhập thành công",
    )
    if ip_address:
        LoginThrottle.objects.filter(ip_address=ip_address).delete()
    request.session["security_ip_address"] = ip_address
    request.session["security_user_agent"] = user_agent
    if user.is_staff:
        request.session["staff_last_activity"] = timezone.now().timestamp()
        request.session.set_expiry(settings.STAFF_SESSION_IDLE_TIMEOUT_SECONDS)
        backend = request.session.get("_auth_user_backend", "")
        if backend.startswith("allauth.") and Authenticator.objects.filter(
            user=user,
            type=Authenticator.Type.TOTP,
        ).exists():
            request.session["staff_mfa_verified"] = True
