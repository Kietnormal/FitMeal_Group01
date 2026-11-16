import re
import secrets
import uuid
from datetime import date, timedelta

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db.models import Q
from django.utils import timezone
from allauth.account.models import EmailAddress

from .models import (
    CustomerAddress,
    OrderReview,
    PendingEmailChange,
    SecurityPolicy,
    validate_avatar_size,
)
from .security import is_ip_temporarily_blocked, record_blocked_login

User = get_user_model()


def normalize_phone(value):
    phone = re.sub(r"\D", "", value)
    if phone.startswith("84") and len(phone) == 11:
        return "0" + phone[2:]
    return phone


class CustomerLoginForm(forms.Form):
    login = forms.CharField(max_length=254)
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    remember = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get("login", "").strip()
        password = cleaned_data.get("password")
        if not identifier or not password:
            return cleaned_data
        if self.request and is_ip_temporarily_blocked(self.request):
            record_blocked_login(self.request, identifier)
            raise ValidationError("IP này đã bị khóa tạm thời do đăng nhập sai nhiều lần.")

        lookup = Q(email__iexact=identifier)
        phone = normalize_phone(identifier)
        if phone:
            lookup |= Q(phone=phone)
        candidates = User.objects.filter(lookup, is_active=True).distinct()
        if candidates.count() != 1:
            user_login_failed.send(
                sender=self.__class__,
                credentials={"username": identifier},
                request=self.request,
            )
            if self.request and is_ip_temporarily_blocked(self.request):
                raise ValidationError("IP này đã bị khóa tạm thời do đăng nhập sai nhiều lần.")
            raise ValidationError("Email/số điện thoại hoặc mật khẩu không chính xác.")

        user = authenticate(
            self.request,
            username=candidates.get().get_username(),
            password=password,
        )
        if user is None:
            if self.request and is_ip_temporarily_blocked(self.request):
                raise ValidationError("IP này đã bị khóa tạm thời do đăng nhập sai nhiều lần.")
            raise ValidationError("Email/số điện thoại hoặc mật khẩu không chính xác.")
        cleaned_data["user"] = user
        return cleaned_data


class CustomerRegistrationForm(forms.Form):
    name = forms.CharField(max_length=120, strip=True)
    email = forms.EmailField(max_length=254)
    phone = forms.CharField(max_length=30)
    password = forms.CharField(strip=False, widget=forms.PasswordInput)
    password_confirm = forms.CharField(strip=False, widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email này đã được đăng ký.")
        return email

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        if not 8 <= len(phone) <= 15:
            raise ValidationError("Số điện thoại phải có từ 8 đến 15 chữ số.")
        if User.objects.filter(phone=phone).exists():
            raise ValidationError("Số điện thoại này đã được đăng ký.")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Mật khẩu nhập lại chưa khớp.")
        if password:
            first_and_last = cleaned_data.get("name", "").split()
            user = User(
                username=f"customer-{uuid.uuid4().hex}",
                email=cleaned_data.get("email", ""),
                first_name=first_and_last[0] if first_and_last else "",
                last_name=" ".join(first_and_last[1:]),
            )
            try:
                password_validation.validate_password(password, user=user)
            except ValidationError as error:
                self.add_error("password", error)
        return cleaned_data

    def save(self):
        name_parts = self.cleaned_data["name"].split()
        user = User.objects.create_user(
            username=f"customer-{uuid.uuid4().hex}",
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=name_parts[0],
            last_name=" ".join(name_parts[1:]),
            phone=self.cleaned_data["phone"],
            is_staff=False,
            is_superuser=False,
        )
        return user


class EmployeeCreationForm(forms.Form):
    name = forms.CharField(
        label="Họ và tên",
        max_length=120,
        strip=True,
    )
    email = forms.EmailField(label="Email đăng nhập", max_length=254)
    phone = forms.CharField(label="Số điện thoại", max_length=30, required=False)
    cccd = forms.CharField(label="Số CCCD (không bắt buộc)", max_length=12, required=False)
    role = forms.ChoiceField(
        label="Vai trò",
        choices=User.StaffRole.choices,
        initial=User.StaffRole.SALES,
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Email này đã được sử dụng.")
        return email

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone", ""))
        if phone and not 8 <= len(phone) <= 15:
            raise ValidationError("Số điện thoại phải có từ 8 đến 15 chữ số.")
        if phone and User.objects.filter(phone=phone).exists():
            raise ValidationError("Số điện thoại này đã được sử dụng.")
        return phone

    def clean_cccd(self):
        cccd = self.cleaned_data.get("cccd", "").strip()
        if cccd and not re.fullmatch(r"[0-9]{12}", cccd):
            raise ValidationError("Số CCCD phải gồm đúng 12 chữ số.")
        if cccd and User.objects.filter(cccd=cccd).exists():
            raise ValidationError("Số CCCD này đã được sử dụng.")
        return cccd

    def save(self):
        name_parts = self.cleaned_data["name"].split()
        staff_role = self.cleaned_data["role"]
        user = User(
            username=f"employee-{uuid.uuid4().hex}",
            email=self.cleaned_data["email"],
            first_name=name_parts[0],
            last_name=" ".join(name_parts[1:]),
            phone=self.cleaned_data["phone"],
            cccd=self.cleaned_data["cccd"] or None,
            staff_role=staff_role,
            is_staff=True,
            is_superuser=staff_role == User.StaffRole.ADMIN,
            must_change_password=True,
        )
        temporary_password = secrets.token_urlsafe(24)
        password_validation.validate_password(temporary_password, user=user)
        user.set_password(temporary_password)
        user.save()
        return user, temporary_password


class EmployeeRoleUpdateForm(forms.Form):
    role = forms.ChoiceField(choices=User.StaffRole.choices)


class EmployeeProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("phone",)
        labels = {"phone": "Số điện thoại liên lạc"}
        widgets = {
            "phone": forms.TextInput(
                attrs={"autocomplete": "tel", "placeholder": "Nhập số điện thoại"}
            ),
        }

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone", ""))
        if phone and not 8 <= len(phone) <= 15:
            raise ValidationError("Số điện thoại phải có từ 8 đến 15 chữ số.")
        if phone and User.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Số điện thoại này đã được sử dụng.")
        return phone


class CustomerProfileForm(forms.Form):
    name = forms.CharField(max_length=120, strip=True)
    email = forms.EmailField(max_length=254)
    phone = forms.CharField(max_length=30, required=False)
    gender = forms.ChoiceField(choices=User.Gender.choices, required=False)
    birth_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    avatar = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png"}),
        validators=[FileExtensionValidator(["jpg", "jpeg", "png"]), validate_avatar_size],
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        initial = kwargs.pop("initial", {})
        initial.setdefault("name", user.get_full_name())
        initial.setdefault("email", user.email)
        initial.setdefault("phone", user.phone)
        initial.setdefault("gender", user.gender)
        initial.setdefault("birth_date", user.birth_date)
        super().__init__(*args, initial=initial, **kwargs)

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        if birth_date and birth_date > date.today():
            raise ValidationError("Ngày sinh không thể nằm trong tương lai.")
        return birth_date

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise ValidationError("Email này đã được sử dụng.")
        if PendingEmailChange.objects.filter(email__iexact=email).exclude(user=self.user).exists():
            raise ValidationError("Email này đang được yêu cầu bởi tài khoản khác.")
        if EmailAddress.objects.filter(email__iexact=email).exclude(user=self.user).exists():
            raise ValidationError("Email này đã được liên kết với tài khoản khác.")
        return email

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get("phone", ""))
        if phone and not 8 <= len(phone) <= 15:
            raise ValidationError("Số điện thoại phải có từ 8 đến 15 chữ số.")
        if phone and User.objects.filter(phone=phone).exclude(pk=self.user.pk).exists():
            raise ValidationError("Số điện thoại này đã được sử dụng.")
        return phone

    def save(self):
        name_parts = self.cleaned_data["name"].split()
        self.user.first_name = name_parts[0]
        self.user.last_name = " ".join(name_parts[1:])
        new_phone = self.cleaned_data["phone"]
        if new_phone != self.user.phone:
            self.user.phone = new_phone
            self.user.phone_verified = False
        self.user.gender = self.cleaned_data["gender"] or User.Gender.UNSPECIFIED
        self.user.birth_date = self.cleaned_data["birth_date"]
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            self.user.avatar = avatar
        elif avatar is False:
            self.user.avatar = ""
        self.user.save(
            update_fields=[
                "first_name",
                "last_name",
                "phone",
                "phone_verified",
                "gender",
                "birth_date",
                *(["avatar"] if avatar is not None else []),
            ]
        )
        pending_email = None
        if self.cleaned_data["email"] != self.user.email:
            pending_email, _ = PendingEmailChange.objects.update_or_create(
                user=self.user,
                defaults={
                    "email": self.cleaned_data["email"],
                    "expires_at": timezone.now() + timedelta(days=1),
                },
            )
        else:
            PendingEmailChange.objects.filter(user=self.user).delete()
        return pending_email


class CustomerAddressForm(forms.ModelForm):
    class Meta:
        model = CustomerAddress
        fields = ("label", "address", "district", "city", "is_default")


class StarRatingSelect(forms.RadioSelect):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )
        option["attrs"]["aria-label"] = f"{option['value']} sao"
        return option


class OrderReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(
        label="Đánh giá",
        choices=[(value, "") for value in range(5, 0, -1)],
        widget=StarRatingSelect(),
    )

    class Meta:
        model = OrderReview
        fields = ("rating", "comment")
        widgets = {
            "comment": forms.Textarea(
                attrs={"rows": 3, "maxlength": 1000, "placeholder": "Chia sẻ cảm nhận của bạn (không bắt buộc)."}
            ),
        }
        labels = {"comment": "Nhận xét (không bắt buộc)"}

    def clean_rating(self):
        return int(self.cleaned_data["rating"])


class StaffMfaVerifyForm(forms.Form):
    code = forms.CharField(
        label="Mã xác thực",
        min_length=6,
        max_length=20,
        strip=True,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "autofocus": True,
            }
        ),
    )


class SecurityPolicyForm(forms.ModelForm):
    class Meta:
        model = SecurityPolicy
        fields = ("require_admin_2fa", "require_manager_2fa")
