from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.create_order, name="create"),
    path("track/<uuid:token>/", views.track_order, name="track"),
    path(
        "track/<uuid:token>/confirm-delivery/",
        views.track_confirm_delivery,
        name="track_confirm_delivery",
    ),
    path(
        "track/<uuid:token>/report-delivery-issue/",
        views.track_report_delivery_issue,
        name="track_report_delivery_issue",
    ),
    path("<int:order_id>/cancel/", views.customer_cancel_order, name="customer_cancel"),
    path(
        "<int:order_id>/confirm-delivery/",
        views.customer_confirm_delivery,
        name="customer_confirm_delivery",
    ),
    path(
        "<int:order_id>/report-delivery-issue/",
        views.customer_report_delivery_issue,
        name="customer_report_delivery_issue",
    ),
    path(
        "<int:order_id>/care-request/",
        views.customer_submit_order_care_request,
        name="customer_care_request",
    ),
    path("<int:order_id>/reorder/", views.reorder_order, name="reorder"),
]
