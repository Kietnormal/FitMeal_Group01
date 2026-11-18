from django.urls import path

from apps.accounts import views as account_views
from apps.core import admin_views as core_admin_views

from . import views

app_name = "staff_orders"

urlpatterns = [
    path("", views.staff_dashboard, name="dashboard"),
    path("employees/", account_views.staff_employee_management, name="employees"),
    path(
        "employees/<int:employee_id>/role/",
        account_views.staff_employee_role_update,
        name="update_employee_role",
    ),
    path(
        "employees/<int:employee_id>/terminate/",
        account_views.staff_employee_terminate,
        name="terminate_employee",
    ),
    path("profile/", account_views.staff_profile_update, name="update_staff_profile"),
    path("security/unlock-ip/", account_views.unlock_login_ip, name="security_unlock_ip"),
    path(
        "security/end-other-sessions/",
        account_views.end_other_staff_sessions,
        name="security_end_other_sessions",
    ),
    path("system/backups/create/", core_admin_views.create_backup, name="create_backup"),
    path(
        "system/backups/<str:filename>/",
        core_admin_views.download_backup,
        name="download_backup",
    ),
    path("<int:order_id>/status/", views.staff_update_order_status, name="update_status"),
    path("<int:order_id>/cancel-request/", views.staff_request_order_cancellation, name="request_cancellation"),
    path("<int:order_id>/cancel/", views.manager_cancel_order, name="cancel_order"),
    path(
        "cancellation-requests/<int:cancellation_id>/contact/",
        views.staff_record_cancellation_contact,
        name="record_cancellation_contact",
    ),
    path(
        "cancellation-requests/<int:cancellation_id>/resolve/",
        views.manager_resolve_cancellation,
        name="resolve_cancellation",
    ),
    path(
        "delivery-issues/<int:issue_id>/resolve/",
        views.manager_resolve_delivery_issue,
        name="resolve_delivery_issue",
    ),
    path(
        "customer-care-requests/<int:care_request_id>/resolve/",
        views.manager_resolve_order_care_request,
        name="resolve_customer_care_request",
    ),
    path(
        "orders/<int:order_id>/personal-data/",
        views.access_order_pii,
        name="access_order_pii",
    ),
    path(
        "products/<int:product_id>/request-restock/",
        views.staff_request_inventory_restock,
        name="request_inventory_restock",
    ),
    path(
        "inventory-restock-requests/<int:restock_request_id>/fulfill/",
        views.manager_fulfill_inventory_restock,
        name="fulfill_inventory_restock",
    ),
    path("products/create/", views.staff_create_product, name="create_product"),
    path(
        "products/<int:product_id>/availability/",
        views.staff_toggle_product_availability,
        name="toggle_product_availability",
    ),
    path("products/<int:product_id>/update/", views.staff_update_product, name="update_product"),
]
