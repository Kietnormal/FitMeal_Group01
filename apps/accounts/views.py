from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_login_failed
from django.contrib.sessions.models import Session
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator

from .forms import (
    CustomerAddressForm,
    CustomerLoginForm,
    CustomerProfileForm,
    CustomerRegistrationForm,
    EmployeeProfileForm,
    EmployeeRoleUpdateForm,
    OrderReviewForm,
    SecurityPolicyForm,
    StaffMfaVerifyForm,
)
from .models import CustomerAddress, LoginThrottle, PendingEmailChange, SecurityPolicy
from .security import (
    is_ip_temporarily_blocked,
    record_blocked_login,
    staff_requires_2fa,
)
from apps.orders.models import Order

User = get_user_model()


def _show_form_errors(request, form):
    for errors in form.errors.values():
        for error in errors:
            messages.error(request, error)


@require_POST
def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = CustomerLoginForm(request.POST, request=request)
    if not form.is_valid():
        _show_form_errors(request, form)
        return redirect(f"{reverse('core:account')}#login")

    user = form.cleaned_data["user"]
    has_totp = Authenticator.objects.filter(
        user=user,
        type=Authenticator.Type.TOTP,
    ).exists()
    requires_2fa = staff_requires_2fa(user)
    if user.is_staff and (has_totp or requires_2fa):
        if not has_totp:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.info(request, "Hãy thiết lập xác thực hai bước để tiếp tục.")
            return redirect("mfa_activate_totp")
        request.session["pending_staff_mfa_user_id"] = user.pk
        request.session["pending_staff_mfa_created_at"] = timezone.now().timestamp()
        request.session["pending_staff_mfa_remember"] = form.cleaned_data["remember"]
        request.session.set_expiry(300)
        return redirect("accounts:verify_staff_mfa")

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(60 * 60 * 24 * 14 if form.cleaned_data["remember"] else 0)
    messages.success(request, "Đăng nhập thành công.")
    if user.is_staff and not user.is_superuser:
        return redirect("staff_orders:dashboard")
    if user.is_superuser:
        return redirect("staff_orders:dashboard")
    return redirect("core:home")


@require_http_methods(["GET", "POST"])
def verify_staff_mfa(request):
    pending_user_id = request.session.get("pending_staff_mfa_user_id")
    pending_created_at = request.session.get("pending_staff_mfa_created_at")
    pending_login = pending_user_id is not None
    if pending_login:
        try:
            pending_expired = timezone.now().timestamp() - float(pending_created_at) > 300
        except (TypeError, ValueError):
            pending_expired = True
        if pending_expired:
            request.session.pop("pending_staff_mfa_user_id", None)
            request.session.pop("pending_staff_mfa_created_at", None)
            request.session.pop("pending_staff_mfa_remember", None)
            messages.error(request, "Phiên xác thực đã hết hạn. Vui lòng đăng nhập lại.")
            return redirect(f"{reverse('core:account')}#login")
        user = get_object_or_404(
            get_user_model(),
            pk=pending_user_id,
            is_active=True,
            is_staff=True,
        )
    elif request.user.is_authenticated and request.user.is_staff:
        user = request.user
    else:
        return redirect(f"{reverse('core:account')}#login")

    form = StaffMfaVerifyForm(request.POST or None)
    if request.method == "POST":
        if is_ip_temporarily_blocked(request):
            record_blocked_login(request, user.email or user.get_username())
            form.add_error(None, "IP này đã bị khóa tạm thời do đăng nhập sai nhiều lần.")
        elif form.is_valid():
            authenticators = Authenticator.objects.filter(
                user=user,
                type__in=(
                    Authenticator.Type.TOTP,
                    Authenticator.Type.RECOVERY_CODES,
                ),
            )
            valid_code = any(
                authenticator.wrap().validate_code(form.cleaned_data["code"])
                for authenticator in authenticators
            )
            if valid_code:
                remember = request.session.pop("pending_staff_mfa_remember", False)
                request.session.pop("pending_staff_mfa_user_id", None)
                request.session.pop("pending_staff_mfa_created_at", None)
                if pending_login:
                    login(
                        request,
                        user,
                        backend="django.contrib.auth.backends.ModelBackend",
                    )
                request.session["staff_mfa_verified"] = True
                request.session.set_expiry(
                    60 * 60 * 24 * 14
                    if remember
                    else settings.STAFF_SESSION_IDLE_TIMEOUT_SECONDS
                )
                messages.success(request, "Xác thực hai bước thành công.")
                return redirect("staff_orders:dashboard")

            user_login_failed.send(
                sender=StaffMfaVerifyForm,
                credentials={"username": user.get_username(), "mfa_code": "invalid"},
                request=request,
            )
            form.add_error("code", "Mã xác thực không chính xác hoặc đã được sử dụng.")
    return render(request, "accounts/verify_staff_mfa.html", {"form": form})


@login_required
@require_POST
def update_security_policy(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    policy = SecurityPolicy.objects.first() or SecurityPolicy(pk=1)
    form = SecurityPolicyForm(request.POST, instance=policy)
    if form.is_valid():
        updated_policy = form.save(commit=False)
        updated_policy.pk = 1
        updated_policy.updated_by = request.user
        missing_roles = []
        for enabled, role, label in (
            (
                form.cleaned_data["require_admin_2fa"],
                User.StaffRole.ADMIN,
                "quản trị viên",
            ),
            (
                form.cleaned_data["require_manager_2fa"],
                User.StaffRole.MANAGER,
                "quản lý",
            ),
        ):
            if not enabled:
                continue
            staff_ids = User.objects.filter(
                is_active=True,
                is_staff=True,
                staff_role=role,
            ).values_list("pk", flat=True)
            enrolled_ids = Authenticator.objects.filter(
                user_id__in=staff_ids,
                type=Authenticator.Type.TOTP,
            ).values_list("user_id", flat=True)
            if User.objects.filter(pk__in=staff_ids).exclude(
                pk__in=enrolled_ids
            ).exists():
                missing_roles.append(label)
        if missing_roles:
            messages.error(
                request,
                "Chưa bật được chính sách: hãy để tất cả tài khoản "
                f"{' và '.join(missing_roles)} thiết lập TOTP trước.",
            )
        else:
            updated_policy.save()
            messages.success(request, "Đã cập nhật chính sách xác thực hai bước.")
    else:
        messages.error(request, "Dữ liệu chính sách bảo mật không hợp lệ.")
    return redirect(f"{reverse('staff_orders:dashboard')}?section=security")


@require_POST
def register_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")
    form = CustomerRegistrationForm(request.POST)
    if not form.is_valid():
        _show_form_errors(request, form)
        return redirect(f"{reverse('core:account')}#register")

    user = form.save()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Tạo tài khoản thành công. Bạn đã đăng nhập.")
    return redirect("core:home")


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "Bạn đã đăng xuất.")
    return redirect("core:account")


@login_required
@require_http_methods(["GET", "POST"])
def password_change(request):
    form = PasswordChangeForm(user=request.user, data=request.POST or None)
    form.fields["old_password"].label = (
        "Mật khẩu tạm hiện tại"
        if request.user.must_change_password
        else "Mật khẩu hiện tại"
    )
    form.fields["new_password2"].label = "Nhập lại mật khẩu mới"
    form.fields["old_password"].widget.attrs.update(
        {
            "class": "first-login-input",
            "autocomplete": "current-password",
            "placeholder": (
                "Mật khẩu trong email quản trị viên gửi"
                if request.user.must_change_password
                else "Nhập mật khẩu hiện tại"
            ),
        }
    )
    for field_name in ("new_password1", "new_password2"):
        form.fields[field_name].widget.attrs.update(
            {
                "class": "first-login-input",
                "autocomplete": "new-password",
            }
        )
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        messages.success(request, "Mật khẩu đã được cập nhật.")
        if user.is_staff:
            return redirect("staff_orders:dashboard")
        return redirect("core:home")
    return render(request, "accounts/password_change.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def staff_employee_management(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    return redirect(f"{reverse('staff_orders:dashboard')}?section=employees")


@login_required
@require_POST
def staff_employee_terminate(request, employee_id):
    if not request.user.is_superuser:
        raise PermissionDenied

    user_model = get_user_model()
    with transaction.atomic():
        employee = get_object_or_404(
            user_model.objects.select_for_update()
            .filter(is_staff=True, is_superuser=False)
            .exclude(pk=request.user.pk),
            pk=employee_id,
        )
        if employee.is_active:
            employee.is_active = False
            employee.save(update_fields=["is_active"])
            messages.success(
                request,
                f"Đã cho {employee.get_full_name() or employee.username} nghỉ việc và khóa đăng nhập.",
            )
        else:
            messages.info(request, "Tài khoản này đã nghỉ việc và đang bị khóa.")
    return redirect(f"{reverse('staff_orders:dashboard')}?section=employees#employees")


@login_required
@require_POST
def staff_employee_role_update(request, employee_id):
    if not request.user.is_superuser:
        raise PermissionDenied

    user_model = get_user_model()
    with transaction.atomic():
        employee = get_object_or_404(
            user_model.objects.select_for_update(),
            pk=employee_id,
            is_staff=True,
        )
        form = EmployeeRoleUpdateForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data["role"]
            employee.staff_role = role
            employee.is_superuser = role == user_model.StaffRole.ADMIN
            employee.save(update_fields=["staff_role", "is_superuser"])
            messages.success(
                request,
                f"Đã cập nhật vai trò của {employee.get_full_name() or employee.username}.",
            )
        else:
            messages.error(request, "Vai trò nhân viên không hợp lệ.")
    return redirect(f"{reverse('staff_orders:dashboard')}?section=employees#employees")


@login_required
@require_POST
def staff_profile_update(request):
    user = request.user
    if (
        not user.is_staff
        or user.is_superuser
        or user.staff_role not in {user.StaffRole.MANAGER, user.StaffRole.SALES}
    ):
        raise PermissionDenied

    form = EmployeeProfileForm(request.POST, instance=user)
    if form.is_valid():
        form.save()
        messages.success(request, "Đã cập nhật số điện thoại liên lạc.")
    else:
        _show_form_errors(request, form)
    return redirect(f"{reverse('staff_orders:dashboard')}?workspace=profile#staff-profile")


@login_required
@require_POST
def unlock_login_ip(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    ip_address = request.POST.get("ip_address", "").strip()
    throttle = get_object_or_404(LoginThrottle, ip_address=ip_address)
    throttle.delete()
    messages.success(request, f"Đã gỡ khóa đăng nhập cho IP {ip_address}.")
    return redirect(f"{reverse('staff_orders:dashboard')}?section=security")


@login_required
@require_POST
def end_other_staff_sessions(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    current_session_key = request.session.session_key
    staff_user_ids = {
        str(user_id)
        for user_id in get_user_model().objects.filter(is_staff=True).values_list("pk", flat=True)
    }
    ended = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if session.session_key == current_session_key:
            continue
        decoded = session.get_decoded()
        if str(decoded.get("_auth_user_id", "")) in staff_user_ids:
            session.delete()
            ended += 1
    messages.success(request, f"Đã đăng xuất {ended} phiên nhân viên khác.")
    return redirect(f"{reverse('staff_orders:dashboard')}?section=security")


@login_required
@require_POST
def profile_update(request):
    form = CustomerProfileForm(request.POST, request.FILES, user=request.user)
    if form.is_valid():
        pending_email = form.save()
        if pending_email:
            confirmation_url = request.build_absolute_uri(
                reverse("accounts:confirm_email", args=[pending_email.token])
            )
            send_mail(
                "Xác nhận thay đổi email FitMeal",
                (
                    f"Bạn đã yêu cầu đổi email tài khoản FitMeal sang {pending_email.email}.\n"
                    f"Mở liên kết sau để xác nhận trong vòng 24 giờ:\n{confirmation_url}\n"
                    "Nếu bạn không thực hiện yêu cầu này, hãy bỏ qua email."
                ),
                settings.DEFAULT_FROM_EMAIL,
                [pending_email.email],
                fail_silently=False,
            )
            messages.success(request, "Đã gửi liên kết xác nhận đến email mới. Email hiện tại chưa thay đổi.")
        else:
            messages.success(request, "Thông tin tài khoản đã được cập nhật.")
    else:
        _show_form_errors(request, form)
    return redirect(f"{reverse('core:account')}?tab=profile#profile")


@login_required
@require_POST
def address_create(request):
    form = CustomerAddressForm(request.POST)
    if form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        with transaction.atomic():
            if address.is_default or not request.user.saved_addresses.exists():
                request.user.saved_addresses.update(is_default=False)
                address.is_default = True
            address.save()
        messages.success(request, "Đã lưu địa chỉ nhận hàng.")
    else:
        _show_form_errors(request, form)
    return redirect(f"{reverse('core:account')}?tab=addresses#addresses")


@login_required
@require_POST
def address_update(request, address_id):
    address = get_object_or_404(CustomerAddress, pk=address_id, user=request.user)
    was_default = address.is_default
    form = CustomerAddressForm(request.POST, instance=address)
    if form.is_valid():
        updated = form.save(commit=False)
        with transaction.atomic():
            if updated.is_default:
                request.user.saved_addresses.exclude(pk=updated.pk).update(is_default=False)
            elif was_default:
                replacement = request.user.saved_addresses.exclude(pk=updated.pk).first()
                if replacement:
                    replacement.is_default = True
                    replacement.save(update_fields=["is_default"])
                else:
                    updated.is_default = True
            updated.save()
        messages.success(request, "Đã cập nhật địa chỉ.")
    else:
        _show_form_errors(request, form)
    return redirect(f"{reverse('core:account')}?tab=addresses#addresses")


@login_required
@require_POST
def address_delete(request, address_id):
    with transaction.atomic():
        address = get_object_or_404(CustomerAddress, pk=address_id, user=request.user)
        was_default = address.is_default
        address.delete()
        if was_default:
            replacement = request.user.saved_addresses.first()
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=["is_default"])
    messages.success(request, "Đã xóa địa chỉ.")
    return redirect(f"{reverse('core:account')}?tab=addresses#addresses")


@login_required
@require_POST
def review_order(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("customer_review"),
        pk=order_id,
        customer=request.user,
        status=Order.Status.DELIVERED,
    )
    existing_review = getattr(order, "customer_review", None)
    form = OrderReviewForm(request.POST, instance=existing_review)
    if form.is_valid():
        review = form.save(commit=False)
        review.order = order
        review.save()
        messages.success(request, "Cảm ơn bạn đã gửi đánh giá đơn hàng.")
    else:
        _show_form_errors(request, form)
    return redirect(f"{reverse('core:account')}?tab=reviews#reviews")


def confirm_email(request, token):
    pending = get_object_or_404(PendingEmailChange, token=token)
    if pending.expires_at <= timezone.now():
        pending.delete()
        messages.error(request, "Liên kết xác nhận đã hết hạn. Hãy gửi lại yêu cầu đổi email.")
        return redirect("core:account")
    if request.method == "POST":
        with transaction.atomic():
            pending = get_object_or_404(PendingEmailChange.objects.select_for_update(), token=token)
            if pending.expires_at <= timezone.now():
                pending.delete()
                messages.error(request, "Liên kết xác nhận đã hết hạn.")
                return redirect("core:account")
            if get_user_model().objects.filter(email__iexact=pending.email).exclude(pk=pending.user_id).exists():
                pending.delete()
                messages.error(request, "Email đã được sử dụng bởi tài khoản khác.")
                return redirect("core:account")
            if EmailAddress.objects.filter(email__iexact=pending.email).exclude(user_id=pending.user_id).exists():
                pending.delete()
                messages.error(request, "Email đã được liên kết với tài khoản khác.")
                return redirect("core:account")
            user = pending.user
            email_address, _ = EmailAddress.objects.get_or_create(
                user=user,
                email=pending.email,
                defaults={"verified": True, "primary": True},
            )
            EmailAddress.objects.filter(user=user, primary=True).exclude(pk=email_address.pk).update(primary=False)
            if not email_address.verified or not email_address.primary:
                email_address.verified = True
                email_address.primary = True
                email_address.save(update_fields=["verified", "primary"])
            user.email = pending.email
            user.save(update_fields=["email"])
            pending.delete()
        messages.success(request, "Email tài khoản đã được xác nhận và cập nhật.")
        return redirect("core:account")

    return render(request, "core/account_email_confirm.html", {"pending_email": pending})
