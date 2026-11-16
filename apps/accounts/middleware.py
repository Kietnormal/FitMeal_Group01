from django.conf import settings
from allauth.mfa.models import Authenticator

from .models import SecurityPolicy
from .security import staff_requires_2fa
from django.shortcuts import redirect


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated or not request.user.must_change_password:
            return None

        view_name = getattr(request.resolver_match, "view_name", "")
        if view_name in {"accounts:password_change", "accounts:logout"}:
            return None

        for url_prefix in (settings.STATIC_URL, settings.MEDIA_URL):
            if url_prefix and request.path_info.startswith(f"/{url_prefix.lstrip('/')}"):
                return None

        return redirect("accounts:password_change")


class StaffMfaEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated or not user.is_staff:
            return None

        has_totp = Authenticator.objects.filter(
            user=user,
            type=Authenticator.Type.TOTP,
        ).exists()
        required = staff_requires_2fa(user, SecurityPolicy.objects.first())
        if not required and not has_totp:
            return None

        view_name = getattr(request.resolver_match, "view_name", "")
        if not has_totp:
            if view_name in {
                "mfa_index",
                "mfa_reauthenticate",
                "mfa_activate_totp",
                "accounts:logout",
                "accounts:password_change",
            }:
                return None
            request.session.pop("staff_mfa_verified", None)
            return redirect("mfa_activate_totp")

        if request.session.get("staff_mfa_verified"):
            return None
        if view_name in {
            "accounts:verify_staff_mfa",
            "accounts:logout",
            "accounts:password_change",
        }:
            return None
        return redirect("accounts:verify_staff_mfa")
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone


class StaffSessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_staff:
            now = timezone.now().timestamp()
            last_activity = request.session.get("staff_last_activity")
            timeout = settings.STAFF_SESSION_IDLE_TIMEOUT_SECONDS
            if last_activity is not None:
                try:
                    is_idle = now - float(last_activity) > timeout
                except (TypeError, ValueError):
                    is_idle = True
                if is_idle:
                    logout(request)
                    return redirect("core:account")
            request.session["staff_last_activity"] = now
            request.session.set_expiry(timeout)
        return self.get_response(request)
