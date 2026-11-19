import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from time import time

from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from allauth.mfa import app_settings as mfa_settings
from allauth.mfa.totp.internal.auth import TOTP, hotp_value

from apps.orders.models import Order

from .models import (
    CustomerAddress,
    LoginEvent,
    LoginThrottle,
    OrderReview,
    PendingEmailChange,
    PointsTransaction,
    SecurityPolicy,
    User,
)


class UserModelTests(TestCase):
    def test_create_user_with_phone(self):
        user = get_user_model().objects.create_user(
            username="khach1", password="Matkhau-manh-123", phone="0900000000"
        )
        self.assertEqual(user.phone, "0900000000")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password("Matkhau-manh-123"))


class LoginSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="security-customer",
            email="security-customer@example.com",
            password="Customer-Strong-2026!",
        )

    def test_fifth_failed_login_temporarily_blocks_ip_and_logs_attempts(self):
        for _ in range(5):
            self.client.post(
                reverse("accounts:login"),
                {"login": self.user.email, "password": "wrong-password"},
                REMOTE_ADDR="198.51.100.27",
                HTTP_USER_AGENT="Security test browser",
            )

        throttle = LoginThrottle.objects.get(ip_address="198.51.100.27")
        self.assertEqual(throttle.failure_count, 5)
        self.assertGreater(throttle.blocked_until, timezone.now())
        self.assertEqual(
            LoginEvent.objects.filter(outcome=LoginEvent.Outcome.FAILURE).count(),
            5,
        )

        self.client.post(
            reverse("accounts:login"),
            {"login": self.user.email, "password": "Customer-Strong-2026!"},
            REMOTE_ADDR="198.51.100.27",
        )
        self.assertEqual(
            LoginEvent.objects.filter(outcome=LoginEvent.Outcome.BLOCKED).count(),
            1,
        )

    def test_successful_login_records_device_and_clears_ip_throttle(self):
        LoginThrottle.objects.create(
            ip_address="198.51.100.28",
            failure_count=2,
            window_started_at=timezone.now(),
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"login": self.user.email, "password": "Customer-Strong-2026!"},
            REMOTE_ADDR="198.51.100.28",
            HTTP_USER_AGENT="FitMeal test browser",
        )

        self.assertRedirects(response, reverse("core:home"))
        self.assertFalse(LoginThrottle.objects.filter(ip_address="198.51.100.28").exists())
        event = LoginEvent.objects.get(outcome=LoginEvent.Outcome.SUCCESS)
        self.assertEqual(event.ip_address, "198.51.100.28")
        self.assertEqual(event.user_agent, "FitMeal test browser")

    def test_staff_session_expires_after_configured_idle_timeout(self):
        manager = User.objects.create_user(
            username="idle-manager",
            email="idle-manager@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(manager)
        session = self.client.session
        session["staff_last_activity"] = timezone.now().timestamp() - 31 * 60
        session.save()

        response = self.client.get(reverse("staff_orders:dashboard"))

        self.assertRedirects(response, reverse("core:account"))
        self.assertNotIn("_auth_user_id", self.client.session)


class StaffMfaTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="mfa-manager",
            email="mfa-manager@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.secret = "JBSWY3DPEHPK3PXP"

    def totp_code(self):
        counter = int(time()) // mfa_settings.TOTP_PERIOD
        value = hotp_value(self.secret, counter)
        return f"{value:0{mfa_settings.TOTP_DIGITS}d}"

    def test_staff_password_login_waits_for_totp_before_authenticating(self):
        TOTP.activate(self.manager, self.secret)

        response = self.client.post(
            reverse("accounts:login"),
            {
                "login": self.manager.email,
                "password": "Manager-Strong-2026!",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:verify_staff_mfa"),
            fetch_redirect_response=False,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

        response = self.client.post(
            reverse("accounts:verify_staff_mfa"),
            {"code": self.totp_code()},
        )

        self.assertRedirects(response, reverse("staff_orders:dashboard"))
        self.assertEqual(self.client.session["staff_mfa_verified"], True)

    def test_required_manager_mfa_blocks_staff_dashboard_without_totp_enrollment(self):
        SecurityPolicy.objects.create(pk=1, require_manager_2fa=True)
        self.client.force_login(self.manager)

        response = self.client.get(reverse("staff_orders:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("mfa_activate_totp"))

    def test_admin_cannot_require_mfa_until_all_target_staff_are_enrolled(self):
        admin = User.objects.create_superuser(
            username="mfa-policy-admin",
            email="mfa-policy-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("accounts:update_security_policy"),
            {"require_admin_2fa": "on", "require_manager_2fa": "on"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SecurityPolicy.objects.filter(require_manager_2fa=True).exists())
        self.assertFalse(SecurityPolicy.objects.filter(require_admin_2fa=True).exists())
        self.assertFalse(
            Authenticator.objects.filter(
                user=self.manager,
                type=Authenticator.Type.TOTP,
            ).exists()
        )


class EmployeeTerminationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="staff-termination-admin",
            email="staff-termination-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.admin_client = Client()
        self.admin_client.force_login(self.admin)

    def test_admin_can_terminate_managers_and_sales_and_they_cannot_log_in(self):
        for role, username in (
            (User.StaffRole.MANAGER, "terminated-manager"),
            (User.StaffRole.SALES, "terminated-sales"),
        ):
            with self.subTest(role=role):
                employee = get_user_model().objects.create_user(
                    username=username,
                    email=f"{username}@example.com",
                    password="Employee-Strong-2026!",
                    is_staff=True,
                    staff_role=role,
                )
                employee_client = Client()
                employee_client.force_login(employee)
                employees_page = self.admin_client.get(
                    reverse("staff_orders:dashboard"),
                    {"section": "employees"},
                )
                terminate_url = reverse(
                    "staff_orders:terminate_employee",
                    args=[employee.pk],
                )
                self.assertContains(employees_page, terminate_url)

                response = self.admin_client.post(
                    terminate_url
                )

                self.assertRedirects(
                    response,
                    f"{reverse('staff_orders:dashboard')}?section=employees#employees",
                )
                employee.refresh_from_db()
                self.assertFalse(employee.is_active)
                self.assertTrue(
                    get_user_model().objects.filter(pk=employee.pk).exists(),
                    "Termination must preserve the employee record and related history.",
                )
                employees_page = self.admin_client.get(
                    reverse("staff_orders:dashboard"),
                    {"section": "employees"},
                )
                self.assertContains(employees_page, "Đã nghỉ việc")
                self.assertNotContains(employees_page, terminate_url)

                existing_session_response = employee_client.get(
                    reverse("staff_orders:dashboard")
                )
                self.assertEqual(existing_session_response.status_code, 302)

                login_response = Client().post(
                    reverse("accounts:login"),
                    {
                        "login": employee.email,
                        "password": "Employee-Strong-2026!",
                    },
                )
                self.assertRedirects(
                    login_response,
                    f"{reverse('core:account')}#login",
                )

    def test_employee_cannot_terminate_staff_and_admin_cannot_terminate_another_admin(self):
        employee = get_user_model().objects.create_user(
            username="termination-target",
            email="termination-target@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        employee_client = Client(raise_request_exception=False)
        employee_client.force_login(employee)

        forbidden_response = employee_client.post(
            reverse("staff_orders:terminate_employee", args=[employee.pk])
        )
        self.assertEqual(forbidden_response.status_code, 403)
        employee.refresh_from_db()
        self.assertTrue(employee.is_active)

        protected_admin_response = self.admin_client.post(
            reverse("staff_orders:terminate_employee", args=[self.admin.pk])
        )
        self.assertEqual(protected_admin_response.status_code, 404)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)


class CustomerAuthenticationTests(TestCase):
    registration_data = {
        "name": "Nguyen Van A",
        "email": "customer@example.com",
        "phone": "0901234567",
        "password": "KhachHang-RatManh-2026!",
        "password_confirm": "KhachHang-RatManh-2026!",
    }

    def create_customer(self, **overrides):
        values = {
            "username": "existing-customer",
            "email": "existing@example.com",
            "phone": "0912345678",
            "address": "Dia chi cu",
            "password": "Customer-Strong-2026!",
            "first_name": "Nguyen",
            "last_name": "Van B",
        }
        values.update(overrides)
        return get_user_model().objects.create_user(**values)

    def create_order(self, customer, status=Order.Status.PENDING):
        return Order.objects.create(
            customer=customer,
            customer_name=customer.get_full_name() or "Nguyen Van A",
            customer_email=customer.email,
            customer_phone=customer.phone,
            address="12 Duong X",
            district="Quan 1",
            city="TP Ho Chi Minh",
            delivery_date=timezone.localdate() + timedelta(days=1),
            delivery_slot=Order.DeliverySlot.MORNING,
            status=status,
            subtotal=Decimal("100000.00"),
            shipping_fee=Decimal("20000.00"),
            total=Decimal("120000.00"),
        )

    def test_registration_creates_customer_and_logs_them_in(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                **self.registration_data,
                "address": "Không nhận địa chỉ ở bước đăng ký",
                "is_staff": "on",
                "is_superuser": "on",
            },
        )

        self.assertRedirects(response, reverse("core:home"))
        user = get_user_model().objects.get(email="customer@example.com")
        self.assertTrue(user.check_password(self.registration_data["password"]))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.phone, "0901234567")
        self.assertEqual(user.address, "")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
    def test_registration_rejects_duplicate_email_and_phone(self):
        self.create_customer()
        duplicate_email = {
            **self.registration_data,
            "email": "EXISTING@example.com",
        }
        duplicate_phone = {
            **self.registration_data,
            "email": "another@example.com",
            "phone": "+84 912 345 678",
        }

        for data in (duplicate_email, duplicate_phone):
            with self.subTest(data=data):
                response = self.client.post(reverse("accounts:register"), data)
                self.assertRedirects(response, f"{reverse('core:account')}#register")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_registration_rejects_mismatched_and_weak_passwords(self):
        mismatched = {**self.registration_data, "password_confirm": "Different-2026!"}
        weak = {
            **self.registration_data,
            "password": "password",
            "password_confirm": "password",
        }

        for data in (mismatched, weak):
            with self.subTest(password=data["password"]):
                response = self.client.post(reverse("accounts:register"), data)
                self.assertRedirects(response, f"{reverse('core:account')}#register")
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_login_accepts_email_or_phone_and_logout_clears_session(self):
        user = self.create_customer()
        for identifier in (user.email, user.phone):
            with self.subTest(identifier=identifier):
                response = self.client.post(
                    reverse("accounts:login"),
                    {"login": identifier, "password": "Customer-Strong-2026!"},
                )
                self.assertRedirects(response, reverse("core:home"))
                self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
                self.client.post(reverse("accounts:logout"))
                self.assertNotIn("_auth_user_id", self.client.session)

    def test_invalid_login_does_not_authenticate(self):
        self.create_customer()

        response = self.client.post(
            reverse("accounts:login"),
            {"login": "existing@example.com", "password": "wrong-password"},
        )

        self.assertRedirects(response, f"{reverse('core:account')}#login")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_profile_update_requires_authentication_and_persists_changes(self):
        response = self.client.post(
            reverse("accounts:profile_update"),
            {"name": "Updated Name", "email": "updated@example.com", "phone": "0900000000"},
        )
        self.assertRedirects(response, f"{reverse('core:account')}?next=/account/actions/profile/")

        user = self.create_customer(phone_verified=True)
        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:profile_update"),
            {
                "name": "Tran Thi C",
                "email": "updated@example.com",
                "phone": "+84 900 000 000",
                "gender": "female",
                "birth_date": "1995-08-12",
            },
        )

        self.assertRedirects(response, f"{reverse('core:account')}?tab=profile#profile")
        user.refresh_from_db()
        self.assertEqual(user.get_full_name(), "Tran Thi C")
        self.assertEqual(user.email, "existing@example.com")
        self.assertEqual(user.phone, "0900000000")
        self.assertFalse(user.phone_verified)
        self.assertEqual(user.gender, user.Gender.FEMALE)
        self.assertEqual(user.birth_date.isoformat(), "1995-08-12")
        self.assertEqual(user.address, "Dia chi cu")
        self.assertEqual(PendingEmailChange.objects.get(user=user).email, "updated@example.com")

    def test_customer_cannot_access_django_admin(self):
        user = self.create_customer()
        self.client.force_login(user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)

    def test_customer_profile_and_order_list_are_server_rendered(self):
        user = self.create_customer()
        self.client.force_login(user)

        response = self.client.get(reverse("core:account"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-account-profile')
        self.assertContains(response, 'action="/account/actions/profile/"')
        self.assertContains(response, "Địa chỉ giao hàng")
        self.assertContains(response, "Điểm thưởng")
        self.assertContains(response, "Đơn hàng của tôi")
        self.assertContains(response, 'class="customer-sidebar-home"')
        self.assertContains(response, "Trở về trang chủ")
        self.assertContains(response, 'class="customer-profile-logout"')
        self.assertContains(response, "Đăng xuất")
        self.assertContains(response, "Đánh giá đơn hàng")
        self.assertContains(response, 'href="mailto:hello@fitmeal.vn"')
        self.assertContains(response, "hello@fitmeal.vn")
        self.assertEqual(response.content.count(b'class="customer-nav-icon"'), 6)

    def test_customer_can_review_and_update_completed_order(self):
        user = self.create_customer()
        reviewed_order = self.create_order(user, status=Order.Status.DELIVERED)
        OrderReview.objects.create(order=reviewed_order, rating=5, comment="Đã đánh giá")
        order = self.create_order(user, status=Order.Status.DELIVERED)
        self.client.force_login(user)

        response = self.client.get(reverse("core:account"), {"tab": "reviews"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)
        self.assertNotContains(response, reviewed_order.order_number)
        self.assertContains(response, 'class="customer-review-stars"')
        self.assertContains(response, 'type="radio"')
        self.assertNotRegex(response.content.decode(), r">\s*[1-5] sao</label>")
        self.assertContains(response, "Gửi đánh giá")

        response = self.client.post(
            reverse("accounts:review_order", args=[order.pk]),
            {"rating": "5", "comment": "Rất ngon"},
        )
        self.assertRedirects(response, f"{reverse('core:account')}?tab=reviews#reviews")
        review = OrderReview.objects.get(order=order)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Rất ngon")

        response = self.client.get(reverse("core:account"), {"tab": "reviews"})
        self.assertNotContains(response, order.order_number)
        self.assertContains(response, "Bạn không có đơn hàng nào đang chờ đánh giá.")

        self.client.post(
            reverse("accounts:review_order", args=[order.pk]),
            {"rating": "3", "comment": "Đã cập nhật"},
        )
        review.refresh_from_db()
        self.assertEqual(OrderReview.objects.filter(order=order).count(), 1)
        self.assertEqual(review.rating, 3)
        self.assertEqual(review.comment, "Đã cập nhật")

    def test_review_rating_must_be_between_one_and_five(self):
        user = self.create_customer()
        order = self.create_order(user, status=Order.Status.DELIVERED)
        self.client.force_login(user)

        self.client.post(
            reverse("accounts:review_order", args=[order.pk]),
            {"rating": "6", "comment": "Invalid rating"},
        )

        self.assertFalse(OrderReview.objects.filter(order=order).exists())

    def test_only_owner_can_review_delivered_orders(self):
        user = self.create_customer()
        other_user = self.create_customer(
            username="another-customer",
            email="another@example.com",
            phone="0900000002",
        )
        pending_order = self.create_order(user)
        other_order = self.create_order(other_user, status=Order.Status.DELIVERED)
        self.client.force_login(user)

        for order in (pending_order, other_order):
            with self.subTest(order=order.pk):
                response = self.client.post(
                    reverse("accounts:review_order", args=[order.pk]),
                    {"rating": "5", "comment": "Không được phép"},
                )
                self.assertEqual(response.status_code, 404)
        self.assertFalse(OrderReview.objects.exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_change_only_takes_effect_after_post_confirmation(self):
        user = self.create_customer()
        self.client.force_login(user)
        self.client.post(
            reverse("accounts:profile_update"),
            {
                "name": user.get_full_name(),
                "email": "new-address@example.com",
                "phone": user.phone,
                "gender": user.Gender.UNSPECIFIED,
            },
        )
        pending = PendingEmailChange.objects.get(user=user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new-address@example.com"])
        user.refresh_from_db()
        self.assertEqual(user.email, "existing@example.com")

        confirmation_url = reverse("accounts:confirm_email", args=[pending.token])
        response = self.client.get(confirmation_url)
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, "existing@example.com")

        response = self.client.post(confirmation_url)

        self.assertRedirects(response, reverse("core:account"))
        user.refresh_from_db()
        self.assertEqual(user.email, "new-address@example.com")
        self.assertTrue(EmailAddress.objects.get(user=user, email=user.email).verified)
        self.assertFalse(PendingEmailChange.objects.filter(user=user).exists())

    def test_address_book_sets_a_replacement_default_after_deletion(self):
        user = self.create_customer()
        self.client.force_login(user)
        first_response = self.client.post(
            reverse("accounts:address_create"),
            {
                "label": "Nhà",
                "address": "12 Đường X",
                "district": "Quận 1",
                "city": "TP Hồ Chí Minh",
                "is_default": "on",
            },
        )
        first = CustomerAddress.objects.get(user=user)
        self.client.post(
            reverse("accounts:address_create"),
            {
                "label": "Công ty",
                "address": "20 Đường Y",
                "district": "Quận 3",
                "city": "TP Hồ Chí Minh",
            },
        )
        second = CustomerAddress.objects.get(user=user, label="Công ty")
        self.assertRedirects(first_response, f"{reverse('core:account')}?tab=addresses#addresses")
        self.assertTrue(first.is_default)
        self.assertFalse(second.is_default)

        self.client.post(
            reverse("accounts:address_update", args=[first.pk]),
            {
                "label": first.label,
                "address": first.address,
                "district": first.district,
                "city": first.city,
            },
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

        self.client.post(reverse("accounts:address_delete", args=[second.pk]))

        first.refresh_from_db()
        self.assertTrue(first.is_default)

    def test_staff_login_redirects_to_employee_workspace(self):
        staff_user = self.create_customer(
            username="staff-user",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"login": staff_user.email, "password": "Customer-Strong-2026!"},
        )

        self.assertRedirects(response, reverse("staff_orders:dashboard"))
        dashboard_response = self.client.get(reverse("staff_orders:dashboard"))
        self.assertEqual(dashboard_response.context["active_workspace"], "work")

    def test_registration_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("core:account"))

        response = client.post(reverse("accounts:register"), self.registration_data)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_google_sign_in_is_shown_only_when_credentials_are_configured(self):
        with override_settings(GOOGLE_OAUTH_CLIENT_ID="", GOOGLE_OAUTH_CLIENT_SECRET=""):
            response = self.client.get(reverse("core:account"))
        self.assertNotContains(response, "Tiếp tục với Google")

        with override_settings(
            GOOGLE_OAUTH_CLIENT_ID="test-client-id",
            GOOGLE_OAUTH_CLIENT_SECRET="test-client-secret",
        ):
            response = self.client.get(reverse("core:account"))

        self.assertContains(response, 'action="/accounts/google/login/"')
        self.assertContains(response, "Tiếp tục với Google")


class StaffAccountManagementTests(TestCase):
    def test_only_superusers_can_create_employee_accounts(self):
        user_model = get_user_model()
        employee_admin = user_model.objects.create_user(
            username="staff-manager",
            email="manager@example.com",
            password="Manager-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.MANAGER,
        )
        self.client.force_login(employee_admin)

        response = self.client.post(
            reverse("staff_orders:dashboard"),
            {
                "section": "employees",
                "action": "create_employee",
                "name": "Nhan Vien",
                "email": "employee@example.com",
                "phone": "0901234567",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(user_model.objects.filter(email="employee@example.com").exists())
        response = self.client.post(
            reverse("staff_orders:update_employee_role", args=[employee_admin.pk]),
            {"role": User.StaffRole.ADMIN},
        )
        self.assertEqual(response.status_code, 403)
        employee_admin.refresh_from_db()
        self.assertFalse(employee_admin.is_superuser)

    def test_superuser_creates_employee_with_random_password_and_selected_role(self):
        admin_user = get_user_model().objects.create_superuser(
            username="employee-admin",
            email="admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("staff_orders:dashboard") + "?section=employees",
            {
                "action": "create_employee",
                "name": "Phùng Tấn Sang",
                "email": "employee@example.com",
                "phone": "0901234567",
                "cccd": "012345678901",
                "role": User.StaffRole.MANAGER,
            },
        )

        self.assertEqual(response.status_code, 200)
        employee = get_user_model().objects.get(email="employee@example.com")
        temporary_password = response.context["employee_credentials"]["password"]
        self.assertTrue(employee.is_staff)
        self.assertFalse(employee.is_superuser)
        self.assertTrue(employee.must_change_password)
        self.assertEqual(employee.staff_role, User.StaffRole.MANAGER)
        self.assertEqual(employee.cccd, "012345678901")
        self.assertGreaterEqual(len(temporary_password), 24)
        self.assertNotEqual(temporary_password, "tansang123@")
        self.assertTrue(employee.check_password(temporary_password))
        self.assertContains(response, temporary_password)
        self.assertContains(response, "••••••••8901")
        self.assertNotContains(response, employee.cccd)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_superuser_can_create_account_with_admin_role(self):
        admin_user = get_user_model().objects.create_superuser(
            username="role-admin",
            email="role-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("staff_orders:dashboard") + "?section=employees",
            {
                "action": "create_employee",
                "name": "Nhan Vien Admin",
                "email": "new-admin@example.com",
                "role": User.StaffRole.ADMIN,
            },
        )

        self.assertEqual(response.status_code, 200)
        employee = get_user_model().objects.get(email="new-admin@example.com")
        self.assertTrue(employee.is_staff)
        self.assertTrue(employee.is_superuser)
        self.assertEqual(employee.staff_role, User.StaffRole.ADMIN)
        self.assertTrue(employee.must_change_password)

    def test_superuser_can_change_employee_role(self):
        admin_user = get_user_model().objects.create_superuser(
            username="role-change-admin",
            email="role-change-admin@example.com",
            password="Admin-Strong-2026!",
        )
        employee = get_user_model().objects.create_user(
            username="role-change-employee",
            email="role-change-employee@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("staff_orders:update_employee_role", args=[employee.pk]),
            {"role": User.StaffRole.ADMIN},
        )

        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?section=employees#employees",
        )
        employee.refresh_from_db()
        self.assertEqual(employee.staff_role, User.StaffRole.ADMIN)
        self.assertTrue(employee.is_superuser)

    def test_employee_creation_rejects_invalid_cccd(self):
        admin_user = get_user_model().objects.create_superuser(
            username="cccd-admin",
            email="cccd-admin@example.com",
            password="Admin-Strong-2026!",
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("staff_orders:dashboard") + "?section=employees",
            {
                "action": "create_employee",
                "name": "Nhan Vien",
                "email": "cccd-employee@example.com",
                "cccd": "12345",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Số CCCD phải gồm đúng 12 chữ số.", status_code=400)
        self.assertFalse(get_user_model().objects.filter(email="cccd-employee@example.com").exists())

    def test_temporary_password_forces_change_before_other_pages(self):
        temporary_password = "Temporary-Strong-2026!"
        employee = get_user_model().objects.create_user(
            username="employee-first-login",
            email="first-login@example.com",
            password=temporary_password,
            is_staff=True,
            staff_role=User.StaffRole.SALES,
            must_change_password=True,
        )
        self.client.force_login(employee)

        response = self.client.get(reverse("core:home"))
        self.assertRedirects(response, reverse("accounts:password_change"))

        response = self.client.get(reverse("accounts:password_change"))
        self.assertContains(response, "Đặt mật khẩu của riêng bạn")
        self.assertContains(response, "Mật khẩu tạm hiện tại")
        self.assertContains(response, "KHU VỰC NHÂN VIÊN")
        self.assertContains(response, "first-login-password-rules")

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": temporary_password,
                "new_password1": "Employee-New-Password-2026!",
                "new_password2": "Employee-New-Password-2026!",
            },
        )

        self.assertRedirects(response, reverse("staff_orders:dashboard"))
        employee.refresh_from_db()
        self.assertFalse(employee.must_change_password)
        self.assertTrue(employee.check_password("Employee-New-Password-2026!"))
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)

    def test_employee_can_update_contact_phone_from_workspace_profile(self):
        employee = get_user_model().objects.create_user(
            username="profile-employee",
            email="profile-employee@example.com",
            password="Employee-Strong-2026!",
            is_staff=True,
            staff_role=User.StaffRole.SALES,
        )
        self.client.force_login(employee)

        response = self.client.post(
            reverse("staff_orders:update_staff_profile"),
            {"phone": "0912345678"},
        )

        self.assertRedirects(
            response,
            f"{reverse('staff_orders:dashboard')}?workspace=profile#staff-profile",
        )
        employee.refresh_from_db()
        self.assertEqual(employee.phone, "0912345678")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetTests(TestCase):
    old_password = "Mat-khau-cu-2026!"
    new_password = "Mat-khau-moi-2026!"

    def setUp(self):
        self.user = User.objects.create_user(
            username="quen-mat-khau",
            email="quen@example.com",
            password=self.old_password,
            first_name="Lan",
        )

    def request_code(self, email="quen@example.com", client=None):
        return (client or self.client).post(reverse("accounts:password_reset_request"), {"email": email})

    def code_from_last_email(self):
        match = re.search(r"\b(\d{6})\b", mail.outbox[-1].body)
        self.assertIsNotNone(match)
        return match.group(1)

    def confirm(self, code, password1=None, password2=None, email="quen@example.com", client=None):
        password1 = password1 or self.new_password
        return (client or self.client).post(
            reverse("accounts:password_reset_confirm"),
            {
                "email": email,
                "code": code,
                "new_password1": password1,
                "new_password2": password2 or password1,
            },
        )

    def test_login_page_links_to_forgot_password(self):
        response = self.client.get(reverse("core:account"))

        self.assertContains(response, reverse("accounts:password_reset_request"))
        self.assertContains(response, "Quên mật khẩu?")
        self.assertNotContains(response, "Vui lòng liên hệ quản trị viên để được hỗ trợ đặt lại")

    def test_forgot_password_pages_render(self):
        self.assertContains(self.client.get(reverse("accounts:password_reset_request")), 'name="email"')
        response = self.client.get(reverse("accounts:password_reset_confirm"))
        for field in ('name="code"', 'name="new_password1"', 'name="new_password2"'):
            self.assertContains(response, field)

    def test_full_flow_emails_code_and_sets_new_password(self):
        response = self.request_code("  QUEN@example.com ")

        self.assertRedirects(response, reverse("accounts:password_reset_confirm"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["quen@example.com"])
        code = self.code_from_last_email()
        confirm_page = self.client.get(reverse("accounts:password_reset_confirm"))
        self.assertContains(confirm_page, 'value="quen@example.com"')

        response = self.confirm(code)

        self.assertRedirects(response, f"{reverse('core:account')}#login", fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertEqual(mail.outbox[-1].subject, "Mật khẩu FitMeal đã được thay đổi")
        login = self.client.post(
            reverse("accounts:login"),
            {"login": "quen@example.com", "password": self.new_password},
        )
        self.assertRedirects(login, reverse("core:home"), fetch_redirect_response=False)

    def test_code_is_stored_hashed_and_expires_after_ten_minutes(self):
        self.request_code()
        code = self.code_from_last_email()
        reset = self.user.password_reset_codes.get()
        self.assertNotIn(code, reset.code_hash)
        self.assertEqual(reset.expires_at - reset.created_at, timedelta(minutes=10))

        reset.expires_at = timezone.now() - timedelta(seconds=1)
        reset.save(update_fields=["expires_at"])
        response = self.confirm(code)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mã xác nhận không đúng hoặc đã hết hạn.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_code_cannot_be_reused(self):
        self.request_code()
        code = self.code_from_last_email()
        self.confirm(code)

        response = self.confirm(code, password1="Mat-khau-thu-ba-2026!")

        self.assertContains(response, "Mã xác nhận không đúng hoặc đã hết hạn.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))

    def test_code_locks_after_five_wrong_attempts(self):
        self.request_code()
        code = self.code_from_last_email()
        wrong_code = f"{(int(code) + 1) % 1_000_000:06d}"
        for _ in range(5):
            self.confirm(wrong_code)

        response = self.confirm(code)

        self.assertContains(response, "Mã xác nhận không đúng hoặc đã hết hạn.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.old_password))

    def test_password_mismatch_or_weak_password_does_not_spend_the_code(self):
        self.request_code()
        code = self.code_from_last_email()

        mismatch = self.confirm(code, password1=self.new_password, password2="Khac-hoan-toan-2026!")
        weak = self.confirm(code, password1="12345678")

        self.assertContains(mismatch, "Mật khẩu nhập lại chưa khớp.")
        self.assertEqual(weak.status_code, 200)
        self.assertEqual(self.user.password_reset_codes.get().failed_attempts, 0)
        self.assertRedirects(self.confirm(code), f"{reverse('core:account')}#login", fetch_redirect_response=False)

    def test_unknown_email_gets_same_response_and_no_mail(self):
        known = self.request_code(client=Client())
        unknown = self.request_code("khong-ton-tai@example.com", client=Client())

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known["Location"], unknown["Location"])
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_is_rate_limited_and_new_code_replaces_old_one(self):
        self.request_code()
        first_code = self.code_from_last_email()
        self.request_code()
        self.assertEqual(len(mail.outbox), 1)

        first = self.user.password_reset_codes.get()
        first.created_at = timezone.now() - timedelta(minutes=2)
        first.save(update_fields=["created_at"])
        self.request_code()
        self.assertEqual(len(mail.outbox), 2)
        second_code = self.code_from_last_email()

        if first_code != second_code:
            self.assertContains(self.confirm(first_code), "Mã xác nhận không đúng hoặc đã hết hạn.")
        self.assertRedirects(self.confirm(second_code), f"{reverse('core:account')}#login", fetch_redirect_response=False)

    def test_reset_logs_out_existing_sessions(self):
        other_device = Client()
        other_device.force_login(self.user)
        self.assertEqual(other_device.get(reverse("core:account")).context["user"], self.user)

        self.request_code()
        self.confirm(self.code_from_last_email())

        self.assertFalse(other_device.get(reverse("core:account")).context["user"].is_authenticated)

    def test_reset_clears_temporary_password_flag(self):
        self.user.must_change_password = True
        self.user.save(update_fields=["must_change_password"])

        self.request_code()
        self.confirm(self.code_from_last_email())

        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
