"""Forgot-password flow: a 6-digit one-time code is e-mailed, then exchanged for a new password."""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import PasswordResetCode

logger = logging.getLogger(__name__)

CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=10)
MAX_FAILED_ATTEMPTS = 5
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_CODES_PER_HOUR = 5


def _hash_code(user, code):
    return salted_hmac("fitmeal.accounts.password-reset", f"{user.pk}:{code}").hexdigest()


def find_user_for_reset(email):
    """Return the single active account with this e-mail, or None."""
    users = list(get_user_model().objects.filter(email__iexact=email.strip(), is_active=True)[:2])
    return users[0] if len(users) == 1 else None


def issue_code(user, *, now=None):
    """Create a fresh code for ``user`` and return it, or None when the user must wait.

    Issuing a code invalidates any earlier unused code for the same user.
    """
    now = now or timezone.now()
    recent = user.password_reset_codes.filter(created_at__gte=now - timedelta(hours=1))
    latest = recent.order_by("-created_at").first()
    if latest and now - latest.created_at < RESEND_COOLDOWN:
        return None
    if recent.count() >= MAX_CODES_PER_HOUR:
        return None

    user.password_reset_codes.filter(used_at__isnull=True, expires_at__gt=now).update(expires_at=now)
    code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"
    PasswordResetCode.objects.create(
        user=user,
        code_hash=_hash_code(user, code),
        created_at=now,
        expires_at=now + CODE_TTL,
    )
    return code


def check_code(user, code, *, now=None):
    """Return the matching active reset code, or None. A wrong guess counts as a failed attempt."""
    now = now or timezone.now()
    reset = (
        user.password_reset_codes.filter(
            used_at__isnull=True,
            expires_at__gt=now,
            failed_attempts__lt=MAX_FAILED_ATTEMPTS,
        )
        .order_by("-created_at")
        .first()
    )
    if reset is None:
        return None
    if not constant_time_compare(reset.code_hash, _hash_code(user, code)):
        PasswordResetCode.objects.filter(pk=reset.pk).update(failed_attempts=F("failed_attempts") + 1)
        return None
    return reset


def send_code_email(user, code):
    minutes = int(CODE_TTL.total_seconds() // 60)
    send_mail(
        "Mã đặt lại mật khẩu FitMeal",
        (
            f"Xin chào {user.get_full_name() or user.email},\n\n"
            f"Mã xác nhận để đặt lại mật khẩu FitMeal của bạn là: {code}\n"
            f"Mã có hiệu lực trong {minutes} phút và chỉ dùng được một lần.\n\n"
            "Không chia sẻ mã này với bất kỳ ai, kể cả nhân viên FitMeal.\n"
            "Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này. Mật khẩu hiện tại vẫn giữ nguyên."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_password_changed_email(user):
    try:
        send_mail(
            "Mật khẩu FitMeal đã được thay đổi",
            (
                f"Xin chào {user.get_full_name() or user.email},\n\n"
                "Mật khẩu tài khoản FitMeal của bạn vừa được đặt lại bằng mã xác nhận gửi qua email.\n"
                "Tất cả các phiên đăng nhập cũ đã bị đăng xuất.\n\n"
                "Nếu bạn không thực hiện thay đổi này, hãy liên hệ FitMeal ngay."
            ),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not send password-changed notice to user %s", user.pk)
