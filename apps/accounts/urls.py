from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("mfa/verify/", views.verify_staff_mfa, name="verify_staff_mfa"),
    path("security/mfa-policy/", views.update_security_policy, name="update_security_policy"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("password/change/", views.password_change, name="password_change"),
    path("profile/", views.profile_update, name="profile_update"),
    path("addresses/", views.address_create, name="address_create"),
    path("addresses/<int:address_id>/update/", views.address_update, name="address_update"),
    path("addresses/<int:address_id>/delete/", views.address_delete, name="address_delete"),
    path("orders/<int:order_id>/review/", views.review_order, name="review_order"),
    path("email/confirm/<uuid:token>/", views.confirm_email, name="confirm_email"),
]
