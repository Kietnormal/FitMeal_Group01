from django.utils import timezone

from .models import LoginEvent, LoginThrottle, SecurityPolicy


def request_ip_address(request):
    return request.META.get("REMOTE_ADDR", "")[:45]


def is_ip_temporarily_blocked(request):
    ip_address = request_ip_address(request)
    return bool(
        ip_address
        and LoginThrottle.objects.filter(
            ip_address=ip_address,
            blocked_until__gt=timezone.now(),
        ).exists()
    )


def record_blocked_login(request, identifier):
    LoginEvent.objects.create(
        login_identifier=identifier[:254],
        ip_address=request_ip_address(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        outcome=LoginEvent.Outcome.BLOCKED,
        details="IP bị khóa tạm thời",
    )


def staff_requires_2fa(user, policy=None):
    if not user.is_staff:
        return False
    policy = policy or SecurityPolicy.objects.first()
    if not policy:
        return False
    if user.is_superuser or user.staff_role == user.StaffRole.ADMIN:
        return policy.require_admin_2fa
    if user.staff_role == user.StaffRole.MANAGER:
        return policy.require_manager_2fa
    return False
