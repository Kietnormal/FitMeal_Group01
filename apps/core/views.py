from django.conf import settings
from django.db.models import Avg, Count, Prefetch, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from allauth.account.models import EmailAddress

from apps.accounts.forms import OrderReviewForm
from apps.accounts.models import OrderReview, PendingEmailChange, User
from apps.orders.delivery import (
    earliest_delivery_date,
    finalize_expired_delivery_confirmations,
    latest_dry_goods_delivery_date,
)
from apps.orders.models import Order, OrderCareRequest, OrderCancellationRequest, OrderItem
from apps.orders.privacy import purge_expired_order_pii
from apps.products.models import Product


HOME_REVIEW_LIMIT = 3


def home(request):
    featured_products = list(Product.objects.filter(is_featured=True)[:8])
    hero_product = next(
        (product for product in featured_products if product.is_available and product.protein > 0),
        None,
    )
    # Reviews are shown without customer names: order PII is encrypted after delivery.
    reviews = list(
        OrderReview.objects.exclude(comment="")
        .filter(rating__gte=4)
        .prefetch_related(Prefetch("order__items", queryset=OrderItem.objects.only("order_id", "product_name")))
        .order_by("-created_at")[:HOME_REVIEW_LIMIT]
    )
    review_stats = OrderReview.objects.aggregate(average=Avg("rating"), total=Count("pk"))
    return render(
        request,
        "core/home.html",
        {
            "active_page": "home",
            "featured_products": featured_products,
            "hero_product": hero_product,
            "reviews": reviews,
            "review_average": review_stats["average"],
            "review_total": review_stats["total"],
        },
    )


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
    # Delivery dates are validated against the shop's timezone, so the server provides
    # them instead of letting the browser derive "tomorrow" from its own local clock.
    today = timezone.localdate()
    return render(
        request,
        "core/checkout.html",
        {
            "active_page": "checkout",
            "delivery_min_date": earliest_delivery_date(today=today),
            "dry_goods_max_delivery_date": latest_dry_goods_delivery_date(today=today),
            "saved_addresses": saved_addresses,
            "default_address": default_address,
            "momo_enabled": settings.MOMO_ENABLED,
            "bank_transfer_enabled": settings.BANK_TRANSFER_ENABLED,
        },
    )


def order_tracking(request):
    return render(request, "core/tracking.html", {"active_page": "tracking"})


def account(request):
    purge_expired_order_pii()
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
                Prefetch(
                    "care_requests",
                    queryset=OrderCareRequest.objects.order_by("-requested_at", "-pk"),
                    to_attr="ordered_care_requests",
                ),
            )[:20]
        )
        for order in orders:
            requests = order.ordered_cancellation_requests
            latest_request = requests[0] if requests else None
            care_requests = order.ordered_care_requests
            pending_care_types = {
                care_request.request_type
                for care_request in care_requests
                if care_request.status == OrderCareRequest.Status.PENDING
            }
            return_request_rejected = any(
                care_request.request_type == OrderCareRequest.RequestType.RETURN
                and care_request.status == OrderCareRequest.Status.REJECTED
                for care_request in care_requests
            )
            care_window_open = order.can_submit_customer_care_request()
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
                    "care_requests": care_requests,
                    "care_window_open": care_window_open,
                    "return_request_rejected": return_request_rejected,
                    "care_deadline": order.customer_care_deadline,
                    "can_request_complaint": (
                        care_window_open
                        and not return_request_rejected
                        and OrderCareRequest.RequestType.COMPLAINT not in pending_care_types
                    ),
                    "can_request_return": (
                        care_window_open
                        and not return_request_rejected
                        and OrderCareRequest.RequestType.RETURN not in pending_care_types
                    ),
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
