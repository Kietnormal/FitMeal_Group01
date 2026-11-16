from django.conf import settings
from django.db.models import Prefetch, Sum
from django.http import JsonResponse
from django.shortcuts import render
from allauth.account.models import EmailAddress

from apps.accounts.forms import OrderReviewForm
from apps.accounts.models import PendingEmailChange, User
from apps.orders.delivery import finalize_expired_delivery_confirmations
from apps.orders.models import Order, OrderCancellationRequest
from apps.products.models import Product


def home(request):
    featured_products = Product.objects.filter(is_featured=True)[:6]
    return render(request, "core/home.html", {"featured_products": featured_products})


def shop(request):
    return render(request, "core/shop.html", {"active_page": "shop"})


def cart(request):
    return render(request, "core/cart.html", {"active_page": "cart"})


def checkout(request):
    default_address = None
    saved_addresses = []
    if request.user.is_authenticated:
        saved_addresses = list(request.user.saved_addresses.all())
        default_address = next((address for address in saved_addresses if address.is_default), None)
    return render(
        request,
        "core/checkout.html",
        {
            "active_page": "checkout",
            "saved_addresses": saved_addresses,
            "default_address": default_address,
            "vnpay_enabled": settings.VNPAY_ENABLED,
        },
    )


def order_tracking(request):
    return render(request, "core/tracking.html", {"active_page": "tracking"})


def account(request):
    finalize_expired_delivery_confirmations()
    authenticated = request.user.is_authenticated
    orders = Order.objects.none()
    customer_order_rows = []
    review_orders = []
    addresses = []
    points = 0
    point_transactions = []
    pending_email = None
    email_verified = False
    if authenticated:
        orders = list(
            Order.objects.filter(customer=request.user)
            .prefetch_related(
                "items",
                Prefetch(
                    "cancellation_requests",
                    queryset=OrderCancellationRequest.objects.order_by("-requested_at", "-pk"),
                    to_attr="ordered_cancellation_requests",
                ),
            )[:20]
        )
        for order in orders:
            requests = order.ordered_cancellation_requests
            latest_request = requests[0] if requests else None
            can_cancel = order.status in {
                Order.Status.PENDING,
                Order.Status.CONFIRMED,
                Order.Status.PREPARING,
                Order.Status.PACKING,
                Order.Status.READY,
            } and not (
                latest_request
                and latest_request.status
                in {
                    OrderCancellationRequest.Status.CONTACT_PENDING,
                    OrderCancellationRequest.Status.MANAGER_REVIEW,
                }
            )
            customer_order_rows.append(
                {
                    "order": order,
                    "cancellation_request": latest_request,
                    "can_cancel": can_cancel,
                    "uses_cancellation_review": order.status
                    in {Order.Status.PREPARING, Order.Status.PACKING, Order.Status.READY},
                    "cancelled_by_name": (
                        latest_request.resolved_by.get_full_name()
                        if order.cancelled_by is None
                        and latest_request
                        and latest_request.resolved_by
                        else order.cancelled_by.get_full_name()
                        if order.cancelled_by
                        else "Cửa hàng"
                    ),
                }
            )
        completed_orders = (
            Order.objects.filter(
                customer=request.user,
                status=Order.Status.DELIVERED,
                customer_review__isnull=True,
            )
            .order_by("-created_at")[:50]
        )
        review_orders = [
            {
                "order": order,
                "review": getattr(order, "customer_review", None),
                "form": OrderReviewForm(
                    instance=getattr(order, "customer_review", None),
                    auto_id=f"review-{order.pk}-%s",
                ),
            }
            for order in completed_orders
        ]
        addresses = list(request.user.saved_addresses.all())
        points = request.user.points_transactions.aggregate(total=Sum("points"))["total"] or 0
        point_transactions = list(request.user.points_transactions.select_related("order")[:20])
        pending_email = PendingEmailChange.objects.filter(user=request.user).first()
        email_verified = EmailAddress.objects.filter(
            user=request.user,
            email__iexact=request.user.email,
            verified=True,
        ).exists()
    requested_tab = request.GET.get("tab", "profile")
    active_tab = requested_tab if requested_tab in {"profile", "points", "addresses", "orders", "reviews"} else "profile"
    return render(
        request,
        "core/account.html",
        {
            "active_page": "account",
            "orders": orders,
            "customer_order_rows": customer_order_rows,
            "review_orders": review_orders,
            "addresses": addresses,
            "points": points,
            "point_transactions": point_transactions,
            "pending_email": pending_email,
            "email_verified": email_verified,
            "active_tab": active_tab,
            "gender_choices": User.Gender.choices,
            "google_oauth_enabled": bool(
                settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
            ),
        },
    )


def policies(request):
    return render(request, "core/policies.html", {"active_page": "policies"})


def healthz(request):
    """Endpoint kiểm tra sống cho giám sát (UptimeRobot, Docker healthcheck...)."""
    return JsonResponse({"status": "ok"})
