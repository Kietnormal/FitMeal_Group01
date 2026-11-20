import csv
import json
import logging
import smtplib
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.contrib.auth import get_user_model

from apps.core.admin_dashboard import (
    get_operations_dashboard_context,
    get_security_dashboard_context,
)
from apps.products.forms import (
    ProductCreateForm,
    ProductInventoryUpdateForm,
    ProductManagerUpdateForm,
    ProductQuickEditForm,
)
from apps.products.models import InventoryRestockRequest, Product, ProductActivity
from apps.products.services import record_product_activity as _record_product_activity
from .inventory import (
    fulfill_inventory_backorders,
    reserve_order_inventory,
    restore_order_inventory,
    update_inventory_shortage,
)
from .shipping import calculate_order_shipping, is_ho_chi_minh_city

from .forms import (
    CancellationContactForm,
    CancellationReasonForm,
    CancellationResolutionForm,
    DeliveryIssueForm,
    DeliveryFailureResolutionForm,
    DeliveryIssueResolutionForm,
    OrderCareRequestForm,
    OrderCareRequestResolutionForm,
    OrderPiiAccessForm,
    OrderStatusUpdateForm,
)
from .models import (
    DeliveryIssue,
    Order,
    OrderCareRequest,
    OrderCancellationRequest,
    OrderItem,
    OrderPiiAccessLog,
)
from .delivery import (
    begin_customer_delivery_confirmation,
    earliest_delivery_date,
    finalize_expired_delivery_confirmations,
    latest_dry_goods_delivery_date,
)
from .privacy import decrypt_order_pii_snapshot, purge_expired_order_pii
from apps.payments.gateway import (
    PaymentGatewayError,
    create_bank_transfer_payment,
    expire_pending_payments,
)
from apps.payments.models import PaymentTransaction

MAX_REQUEST_SIZE = 64 * 1024
MAX_ORDER_ITEMS = 50
MAX_ITEM_QUANTITY = 99
superuser_required = user_passes_test(lambda user: user.is_superuser)
logger = logging.getLogger(__name__)
OPEN_CANCELLATION_STATUSES = (
    OrderCancellationRequest.Status.CONTACT_PENDING,
    OrderCancellationRequest.Status.MANAGER_REVIEW,
)
PRE_DELIVERY_STATUSES = (
    Order.Status.PENDING,
    Order.Status.CONFIRMED,
    Order.Status.PREPARING,
    Order.Status.PACKING,
    Order.Status.READY,
)


def _error(message, status=400):
    return JsonResponse({"error": message}, status=status)


def _period_comparison(current, previous):
    if not previous:
        return {"text": "Chưa có dữ liệu kỳ trước", "direction": "neutral"}
    change = (Decimal(current) - Decimal(previous)) * Decimal("100") / Decimal(previous)
    direction = "up" if change >= 0 else "down"
    return {
        "text": f"{abs(change):.1f}% so với kỳ trước",
        "direction": direction,
    }


def _format_vnd(amount):
    return f"{amount:,.0f}".replace(",", ".")


def _safe_csv_value(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _parse_payload(request):
    if len(request.body) > MAX_REQUEST_SIZE:
        return None, _error("Yêu cầu quá lớn.")
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, _error("Dữ liệu gửi lên không phải JSON hợp lệ.")
    if not isinstance(payload, dict):
        return None, _error("Dữ liệu đơn hàng không hợp lệ.")
    return payload, None


def _required_text(payload, field, label, max_length):
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        return None, f"Vui lòng nhập {label}."
    value = value.strip()
    if len(value) > max_length:
        return None, f"{label.capitalize()} không được vượt quá {max_length} ký tự."
    return value, None


def _serialize_order(order):
    if order.customer_info_redacted:
        return {
            "order_number": order.order_number,
            "status": order.status,
            "status_display": order.get_status_display(),
            "privacy_redacted": True,
        }

    latest_cancellation = order.cancellation_requests.first()
    dry_goods_order = order.is_dry_goods_order
    cancellation_requested = bool(
        latest_cancellation
        and latest_cancellation.source == OrderCancellationRequest.Source.CUSTOMER
        and latest_cancellation.status in OPEN_CANCELLATION_STATUSES
    )
    return {
        "order_number": order.order_number,
        "tracking_token": str(order.tracking_token),
        "status": order.status,
        "status_display": (
            "Giao hàng không thành công"
            if order.status == Order.Status.DELIVERY_ISSUE
            else order.get_status_display()
        ),
        "created_at": order.created_at.isoformat(),
        "delivery_date": order.delivery_date.isoformat(),
        "delivery_slot": order.delivery_slot,
        "delivery_type": "nationwide" if dry_goods_order else "local",
        "delivery_type_display": (
            "Đồ khô · giao toàn quốc" if dry_goods_order else "Đồ tươi · giao TP. Hồ Chí Minh"
        ),
        "payment_method": order.payment_method,
        "payment_method_display": order.get_payment_method_display(),
        "subtotal": str(order.subtotal),
        "shipping_fee": str(order.shipping_fee),
        "total": str(order.total),
        "cancellation_requested": cancellation_requested,
        "cancellation_request_status": (
            latest_cancellation.status if latest_cancellation else ""
        ),
        "cancellation_reason": order.cancellation_reason,
        "refund_status": order.get_refund_status_display(),
        "items": [
            {
                "sku": item.product_sku,
                "name": item.product_name,
                "category": item.product_category,
                "shipping_weight_grams": item.shipping_weight_grams,
                "price": str(item.unit_price),
                "quantity": item.quantity,
                "line_total": str(item.line_total),
            }
            for item in order.items.all()
        ],
    }


def _restore_order_pii_for_display(order):
    if not order.customer_pii_encrypted or order.customer_pii_purged_at:
        return False
    snapshot = decrypt_order_pii_snapshot(order.customer_pii_encrypted)
    order_data = snapshot.get("order", {})
    for field in (
        "customer_name",
        "customer_email",
        "customer_phone",
        "address",
        "district",
        "city",
    ):
        if field in order_data:
            setattr(order, field, order_data[field])
    return True


def _cancel_order(order, actor, reason):
    payment = (
        PaymentTransaction.objects.select_for_update().filter(order=order).first()
        if order.payment_method
        in {
            Order.PaymentMethod.BANK_TRANSFER,
            Order.PaymentMethod.VNPAY,
        }
        else None
    )
    payment_is_paid = payment and payment.status == PaymentTransaction.Status.PAID
    if payment and payment.status == PaymentTransaction.Status.PENDING:
        payment.status = PaymentTransaction.Status.FAILED
        payment.response_code = "CANCELLED"
        payment.save(update_fields=["status", "response_code", "updated_at"])
    order.status = Order.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancelled_by = actor
    order.cancellation_reason = reason
    order.cancellation_reason_category = _categorize_cancellation_reason(reason)
    order.refund_status = (
        Order.RefundStatus.NOT_REQUIRED
        if not payment_is_paid
        else Order.RefundStatus.REQUESTED
    )
    order.save(
        update_fields=[
            "status",
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "cancellation_reason_category",
            "refund_status",
            "updated_at",
        ]
    )
    restore_order_inventory(order, actor=actor)


def _categorize_cancellation_reason(reason):
    normalized_reason = reason.casefold()
    if any(
        phrase in normalized_reason
        for phrase in ("đổi ý", "thay đổi", "đặt nhầm", "không cần")
    ):
        return Order.CancellationReasonCategory.CUSTOMER_CHANGED_MIND
    if any(
        phrase in normalized_reason
        for phrase in ("hết món", "hết hàng", "không còn", "thiếu hàng", "tồn kho")
    ):
        return Order.CancellationReasonCategory.OUT_OF_STOCK
    if any(
        phrase in normalized_reason
        for phrase in ("không liên lạc", "không nghe máy", "không bắt máy")
    ):
        return Order.CancellationReasonCategory.NO_CONTACT
    return Order.CancellationReasonCategory.OTHER


def _finalize_delivery_confirmation(order, now):
    expired = (
        order.delivery_confirmation_deadline is None
        or order.delivery_confirmation_deadline <= now
    )
    order.status = Order.Status.DELIVERED
    order.delivery_confirmation_deadline = None
    order.delivery_confirmed_at = now
    order.delivery_confirmation_method = (
        Order.DeliveryConfirmationMethod.AUTOMATIC
        if expired
        else Order.DeliveryConfirmationMethod.CUSTOMER
    )
    order.save(
        update_fields=[
            "status",
            "delivery_confirmation_deadline",
            "delivery_confirmed_at",
            "delivery_confirmation_method",
            "updated_at",
        ]
    )
    return expired


def _report_delivery_issue(order, details, reported_by, now):
    if order.status != Order.Status.AWAITING_CUSTOMER_CONFIRMATION:
        return "not_waiting"
    if (
        order.delivery_confirmation_deadline is None
        or order.delivery_confirmation_deadline <= now
    ):
        _finalize_delivery_confirmation(order, now)
        return "expired"

    DeliveryIssue.objects.create(
        order=order,
        details=details,
        reported_by=reported_by,
    )
    order.status = Order.Status.DELIVERY_ISSUE
    order.delivery_confirmation_deadline = None
    order.save(update_fields=["status", "delivery_confirmation_deadline", "updated_at"])
    return "reported"


def _send_cancellation_email(order, subject, body, *, recipient_email=None):
    try:
        return send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email or order.customer_email],
            fail_silently=False,
        ) == 1
    except (OSError, smtplib.SMTPException):
        logger.exception("Could not email cancellation update for order %s.", order.order_number)
        return False


def _cancellation_email_message(request, sent):
    if not sent:
        messages.warning(
            request,
            "Đã cập nhật đơn hàng nhưng không gửi được email; khách có thể xem trạng thái trong tài khoản.",
        )


@require_POST
def create_order(request):
    expire_pending_payments()
    if request.content_type.split(";")[0].strip() != "application/json":
        return _error("Content-Type phải là application/json.", status=415)
    payload, error = _parse_payload(request)
    if error:
        return error

    customer_name, error_message = _required_text(payload, "name", "họ và tên", 120)
    if error_message:
        return _error(error_message)
    customer_email, error_message = _required_text(payload, "email", "email", 254)
    if error_message:
        return _error(error_message)
    customer_phone, error_message = _required_text(payload, "phone", "số điện thoại", 20)
    if error_message:
        return _error(error_message)
    address, error_message = _required_text(payload, "address", "địa chỉ", 250)
    if error_message:
        return _error(error_message)
    district, error_message = _required_text(payload, "district", "quận / huyện", 100)
    if error_message:
        return _error(error_message)
    city, error_message = _required_text(payload, "city", "tỉnh / thành phố", 100)
    if error_message:
        return _error(error_message)
    delivery_date_value, error_message = _required_text(payload, "delivery_date", "ngày giao", 10)
    if error_message:
        return _error(error_message)
    try:
        delivery_date = date.fromisoformat(delivery_date_value)
    except ValueError:
        return _error("Ngày giao không đúng định dạng.")
    today = timezone.localdate()
    if delivery_date < earliest_delivery_date(today=today):
        return _error("Ngày giao phải từ ngày mai trở đi.")

    delivery_slot = payload.get("delivery_slot")
    if delivery_slot not in Order.DeliverySlot.values:
        return _error("Khung giờ giao không hợp lệ.")
    payment_method = payload.get("payment", Order.PaymentMethod.COD)
    if payment_method not in {
        Order.PaymentMethod.BANK_TRANSFER,
        Order.PaymentMethod.COD,
    }:
        return _error("Phương thức thanh toán không hợp lệ.")
    if (
        payment_method == Order.PaymentMethod.BANK_TRANSFER
        and not settings.BANK_TRANSFER_ENABLED
    ):
        return _error("Chuyển khoản ngân hàng chưa được cấu hình.")
    if payload.get("accept_policy") is not True:
        return _error("Vui lòng đồng ý với chính sách giao hàng và đổi trả.")
    note = payload.get("note", "")
    if not isinstance(note, str) or len(note) > 2000:
        return _error("Ghi chú không hợp lệ hoặc vượt quá 2000 ký tự.")

    requested_items = payload.get("items")
    if not isinstance(requested_items, list) or not requested_items or len(requested_items) > MAX_ORDER_ITEMS:
        return _error(f"Đơn hàng phải có từ 1 đến {MAX_ORDER_ITEMS} dòng sản phẩm.")
    quantities = {}
    for item in requested_items:
        if not isinstance(item, dict):
            return _error("Dòng sản phẩm trong giỏ hàng không hợp lệ.")
        slug = item.get("id")
        quantity = item.get("quantity")
        if not isinstance(slug, str) or not slug:
            return _error("Mã sản phẩm không hợp lệ.")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= MAX_ITEM_QUANTITY:
            return _error(f"Số lượng mỗi món phải từ 1 đến {MAX_ITEM_QUANTITY}.")
        quantities[slug] = quantities.get(slug, 0) + quantity
        if quantities[slug] > MAX_ITEM_QUANTITY:
            return _error(f"Tổng số lượng mỗi món không được vượt quá {MAX_ITEM_QUANTITY}.")

    payment_url = ""
    with transaction.atomic():
        products = {
            product.slug: product
            for product in Product.objects.select_for_update().filter(
                slug__in=quantities,
                is_available=True,
            )
        }
        if products.keys() != quantities.keys():
            return _error("Một hoặc nhiều sản phẩm không còn bán. Vui lòng cập nhật giỏ hàng.")
        inventory_shortages = []
        for slug, quantity in quantities.items():
            product = products[slug]
            if product.tracks_inventory and product.stock_quantity is None:
                return _error(
                    f"{product.name} chưa được cập nhật tồn kho. Vui lòng liên hệ cửa hàng.",
                    status=409,
                )
            if product.tracks_inventory and quantity > product.stock_quantity:
                inventory_shortages.append(product)

        dry_goods_only = all(
            product.category == Product.Category.DRY_GOODS for product in products.values()
        )
        has_dry_goods = any(
            product.category == Product.Category.DRY_GOODS for product in products.values()
        )
        if not dry_goods_only and not is_ho_chi_minh_city(city):
            return _error("Đồ ăn và thức uống tươi chỉ giao trong khu vực TP. Hồ Chí Minh.")
        if dry_goods_only:
            if delivery_date > latest_dry_goods_delivery_date(today=today):
                return _error("Đồ khô có thời gian giao dự kiến từ 1 đến 5 ngày.")
            if delivery_slot != Order.DeliverySlot.COURIER:
                return _error("Đồ khô được giao theo lịch của đơn vị vận chuyển.")
        elif delivery_slot == Order.DeliverySlot.COURIER:
            return _error("Vui lòng chọn khung giờ giao cho đơn hàng nội thành.")

        if has_dry_goods and any(
            product.shipping_weight_grams < 1
            for product in products.values()
            if product.category == Product.Category.DRY_GOODS
        ):
            return _error("Khối lượng giao hàng của một sản phẩm đồ khô chưa được cập nhật.")

        subtotal = sum(
            (products[slug].price * quantity for slug, quantity in quantities.items()),
            Decimal("0.00"),
        )
        try:
            shipping_fee = calculate_order_shipping(subtotal, quantities, products, city)
        except ValueError as error:
            return _error(str(error))
        total = subtotal + shipping_fee
        try:
            validate_email(customer_email)
        except ValidationError:
            return _error("Địa chỉ email không hợp lệ.")

        order = Order.objects.create(
            customer=request.user if request.user.is_authenticated else None,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            address=address,
            district=district,
            city=city,
            delivery_region=(
                Order.DeliveryRegion.HO_CHI_MINH_CITY
                if is_ho_chi_minh_city(city)
                else Order.DeliveryRegion.OTHER_PROVINCES
            ),
            delivery_date=delivery_date,
            delivery_slot=delivery_slot,
            note=note.strip(),
            payment_method=payment_method,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            total=total,
        )
        order_items = [
            OrderItem(
                order=order,
                product=products[slug],
                product_sku=products[slug].sku,
                product_name=products[slug].name,
                product_category=products[slug].category,
                shipping_weight_grams=products[slug].shipping_weight_grams,
                inventory_deducted=False,
                unit_price=products[slug].price,
                quantity=quantity,
                line_total=products[slug].price * quantity,
            )
            for slug, quantity in quantities.items()
        ]
        reserve_order_inventory(
            order_items,
            actor=request.user if request.user.is_authenticated else None,
        )
        OrderItem.objects.bulk_create(order_items)
        for product in inventory_shortages:
            update_inventory_shortage(product)
        if payment_method == Order.PaymentMethod.BANK_TRANSFER:
            _, payment_url = create_bank_transfer_payment(order, request)

    response_data = _serialize_order(order)
    if payment_url:
        response_data["payment_url"] = payment_url
    return JsonResponse(response_data, status=201)


@require_GET
def track_order(request, token):
    purge_expired_order_pii()
    expire_pending_payments()
    finalize_expired_delivery_confirmations()
    order = get_object_or_404(Order.objects.prefetch_related("items"), tracking_token=token)
    return JsonResponse(_serialize_order(order))


@require_POST
def track_confirm_delivery(request, token):
    with transaction.atomic():
        order = (
            Order.objects.select_for_update()
            .filter(tracking_token=token)
            .first()
        )
        if order is None:
            return _error("Không tìm thấy đơn hàng.", status=404)
        if order.status != Order.Status.AWAITING_CUSTOMER_CONFIRMATION:
            return _error("Đơn này không chờ xác nhận đã nhận hàng.", status=409)
        expired = _finalize_delivery_confirmation(order, timezone.now())

    message = (
        "Thời hạn phản hồi đã hết; đơn được tự xác nhận hoàn tất."
        if expired
        else "Cảm ơn bạn đã xác nhận nhận được hàng."
    )
    return JsonResponse({"status": order.status, "message": message})


@require_POST
def track_report_delivery_issue(request, token):
    form = DeliveryIssueForm(request.POST)
    if not form.is_valid():
        message = "; ".join(form.errors.get("details", [])) or "Thông tin khiếu nại không hợp lệ."
        return _error(message)

    with transaction.atomic():
        order = (
            Order.objects.select_for_update()
            .filter(tracking_token=token)
            .first()
        )
        if order is None:
            return _error("Không tìm thấy đơn hàng.", status=404)
        reporter = (
            request.user
            if request.user.is_authenticated and request.user.pk == order.customer_id
            else None
        )
        outcome = _report_delivery_issue(
            order,
            form.cleaned_data["details"],
            reporter,
            timezone.now(),
        )
        if outcome == "not_waiting":
            return _error("Đơn này không chờ phản hồi về việc nhận hàng.", status=409)

    if outcome == "expired":
        message = "Thời hạn phản hồi đã hết; đơn được tự xác nhận hoàn tất."
    else:
        message = "Đã chuyển khiếu nại giao hàng đến Quản lý để xử lý."
    return JsonResponse({"status": order.status, "message": message})


@login_required
@require_POST
def customer_cancel_order(request, order_id):
    form = CancellationReasonForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(form.errors.get("reason", [])) or "Lý do hủy không hợp lệ.")
        return redirect(f"{reverse('core:account')}?tab=orders#orders")

    email_subject = ""
    email_body = ""
    email_recipient = ""
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
            customer=request.user,
        )
        email_recipient = order.customer_email
        if order.status not in PRE_DELIVERY_STATUSES:
            messages.error(request, "Đơn hàng này không còn ở trạng thái có thể hủy.")
            return redirect(f"{reverse('core:account')}?tab=orders#orders")
        if OrderCancellationRequest.objects.filter(
            order=order,
            status__in=OPEN_CANCELLATION_STATUSES,
        ).exists():
            messages.error(request, "Yêu cầu hủy đơn này đang được xử lý.")
            return redirect(f"{reverse('core:account')}?tab=orders#orders")

        reason = form.cleaned_data["reason"]
        if order.status in {Order.Status.PENDING, Order.Status.CONFIRMED}:
            now = timezone.now()
            cancellation = OrderCancellationRequest.objects.create(
                order=order,
                source=OrderCancellationRequest.Source.CUSTOMER,
                status=OrderCancellationRequest.Status.APPROVED,
                reason=reason,
                requested_by=request.user,
                contact_outcome=OrderCancellationRequest.ContactOutcome.NOT_REQUIRED,
                resolved_by=request.user,
                resolved_at=now,
            )
            _cancel_order(order, request.user, cancellation.reason)
            email_subject = f"Đơn hàng {order.order_number} đã được hủy"
            email_body = (
                f"Đơn hàng {order.order_number} đã được hủy theo yêu cầu của bạn.\n"
                f"Lý do: {reason}\n"
                + (
                    "Cửa hàng đã ghi nhận yêu cầu hoàn tiền."
                    if order.refund_status == Order.RefundStatus.REQUESTED
                    else "Bạn không cần thanh toán đơn hàng này."
                )
            )
            success_message = "Đã hủy đơn hàng."
        else:
            OrderCancellationRequest.objects.create(
                order=order,
                source=OrderCancellationRequest.Source.CUSTOMER,
                status=OrderCancellationRequest.Status.CONTACT_PENDING,
                reason=reason,
                requested_by=request.user,
            )
            email_subject = f"FitMeal đã nhận yêu cầu hủy đơn {order.order_number}"
            email_body = (
                f"FitMeal đã nhận yêu cầu hủy đơn {order.order_number}.\n"
                f"Lý do: {reason}\n"
                "Nhân viên sẽ liên hệ bạn trước khi chuyển yêu cầu cho quản lý."
            )
            success_message = "Đã gửi yêu cầu hủy. Nhân viên sẽ liên hệ bạn để xác nhận."

    email_sent = _send_cancellation_email(
        order,
        email_subject,
        email_body,
        recipient_email=email_recipient,
    )
    _cancellation_email_message(request, email_sent)
    messages.success(request, success_message)
    return redirect(f"{reverse('core:account')}?tab=orders#orders")


@login_required
@require_POST
def customer_confirm_delivery(request, order_id):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
            customer=request.user,
        )
        if order.status != Order.Status.AWAITING_CUSTOMER_CONFIRMATION:
            messages.error(request, "Đơn này không chờ xác nhận đã nhận hàng.")
            return redirect(f"{reverse('core:account')}?tab=orders#orders")
        expired = _finalize_delivery_confirmation(order, timezone.now())
    if expired:
        messages.info(request, "Thời hạn phản hồi đã hết; đơn được tự xác nhận hoàn tất.")
    else:
        messages.success(request, "Cảm ơn bạn đã xác nhận nhận được hàng.")
    return redirect(f"{reverse('core:account')}?tab=orders#orders")


@login_required
@require_POST
def customer_report_delivery_issue(request, order_id):
    form = DeliveryIssueForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(form.errors.get("details", [])) or "Thông tin khiếu nại không hợp lệ.")
        return redirect(f"{reverse('core:account')}?tab=orders#orders")

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
            customer=request.user,
        )
        outcome = _report_delivery_issue(
            order,
            form.cleaned_data["details"],
            request.user,
            timezone.now(),
        )
        if outcome == "expired":
            messages.error(
                request,
                "Thời hạn phản hồi đã hết và đơn được tự xác nhận hoàn tất.",
            )
            return redirect(f"{reverse('core:account')}?tab=orders#orders")
        if outcome == "not_waiting":
            messages.error(request, "Đơn này không chờ phản hồi về việc nhận hàng.")
            return redirect(f"{reverse('core:account')}?tab=orders#orders")
    messages.success(request, "Đã chuyển khiếu nại giao hàng đến Quản lý để xử lý.")
    return redirect(f"{reverse('core:account')}?tab=orders#orders")


@login_required
@require_POST
def customer_submit_order_care_request(request, order_id):
    form = OrderCareRequestForm(request.POST)
    if not form.is_valid():
        messages.error(
            request,
            "; ".join(
                error for error_list in form.errors.values() for error in error_list
            )
            or "Thông tin khiếu nại / đổi trả không hợp lệ.",
        )
        return redirect(f"{reverse('core:account')}?tab=orders#orders")

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=order_id,
            customer=request.user,
        )
        if OrderCareRequest.objects.filter(
            order=order,
            request_type=OrderCareRequest.RequestType.RETURN,
            status=OrderCareRequest.Status.REJECTED,
        ).exists():
            messages.error(
                request,
                "Yêu cầu đổi/trả trước đó đã bị từ chối. Đơn này không thể gửi thêm khiếu nại hoặc yêu cầu đổi/trả.",
            )
            return redirect(f"{reverse('core:account')}?tab=orders#orders")
        if not order.can_submit_customer_care_request():
            messages.error(
                request,
                "Chỉ có thể gửi khiếu nại hoặc yêu cầu đổi/trả trong 7 ngày kể từ khi nhận hàng.",
            )
            return redirect(f"{reverse('core:account')}?tab=orders#orders")

        request_type = form.cleaned_data["request_type"]
        if OrderCareRequest.objects.filter(
            order=order,
            request_type=request_type,
            status=OrderCareRequest.Status.PENDING,
        ).exists():
            messages.error(request, "Yêu cầu này đang chờ Quản lý xử lý.")
            return redirect(f"{reverse('core:account')}?tab=orders#orders")

        care_request = OrderCareRequest.objects.create(
            order=order,
            request_type=request_type,
            details=form.cleaned_data["details"],
            requested_by=request.user,
        )
    messages.success(
        request,
        f"Đã gửi {care_request.get_request_type_display().lower()} cho đơn {order.order_number}.",
    )
    return redirect(f"{reverse('core:account')}?tab=orders#orders")


@login_required
@require_POST
def reorder_order(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),
        pk=order_id,
        customer=request.user,
    )
    available_items = [
        {"id": item.product.slug, "quantity": item.quantity}
        for item in order.items.all()
        if item.product and item.product.is_available
    ]
    if not available_items:
        return _error("Các món trong đơn này hiện không còn bán.", status=409)
    return JsonResponse({"items": available_items})


@superuser_required
def admin_staff_dashboard(request):
    expire_pending_payments()
    orders = Order.objects.all()
    revenue = (
        orders.filter(status=Order.Status.DELIVERED).aggregate(total=Sum("total"))["total"]
        or Decimal("0.00")
    )
    active_order_value = (
        orders.exclude(status=Order.Status.CANCELLED).aggregate(total=Sum("total"))["total"]
        or Decimal("0.00")
    )
    outstanding_order_value = (
        orders.exclude(status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED])
        .aggregate(total=Sum("total"))["total"]
        or Decimal("0.00")
    )
    today = timezone.localdate()
    current_timezone = timezone.get_current_timezone()

    def day_start(day):
        return timezone.make_aware(datetime.combine(day, time.min), current_timezone)

    range_options = {"today": 1, "7d": 7, "30d": 30}
    selected_range = request.GET.get("range", "7d")
    if selected_range not in range_options:
        selected_range = "7d"
    period_days = range_options[selected_range]
    period_start = today - timedelta(days=period_days - 1)
    previous_start = period_start - timedelta(days=period_days)
    period_orders = orders.filter(
        created_at__gte=day_start(period_start),
        created_at__lt=day_start(today + timedelta(days=1)),
    )
    previous_orders = orders.filter(
        created_at__gte=day_start(previous_start),
        created_at__lt=day_start(period_start),
    )
    period_revenue = (
        period_orders.filter(status=Order.Status.DELIVERED).aggregate(total=Sum("total"))["total"]
        or Decimal("0.00")
    )
    previous_revenue = (
        previous_orders.filter(status=Order.Status.DELIVERED).aggregate(total=Sum("total"))["total"]
        or Decimal("0.00")
    )
    period_order_count = period_orders.count()
    previous_order_count = previous_orders.count()
    period_active_orders = period_orders.exclude(status=Order.Status.CANCELLED)
    previous_active_orders = previous_orders.exclude(status=Order.Status.CANCELLED)
    period_active_total = (
        period_active_orders.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    )
    previous_active_total = (
        previous_active_orders.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    )
    period_active_count = period_active_orders.count()
    previous_active_count = previous_active_orders.count()
    average_order_value = (
        period_active_total / period_active_count if period_active_count else Decimal("0.00")
    )
    previous_average_order_value = (
        previous_active_total / previous_active_count if previous_active_count else Decimal("0.00")
    )
    canceled_count = period_orders.filter(status=Order.Status.CANCELLED).count()
    cancellation_rate = (
        canceled_count * 100 / period_order_count if period_order_count else 0
    )

    days_in_period = [
        period_start + timedelta(days=day_offset)
        for day_offset in range(period_days)
    ]
    daily_totals = period_orders.filter(status=Order.Status.DELIVERED).aggregate(
        **{
            f"day_{index}": Sum(
                "total",
                filter=Q(
                    created_at__gte=day_start(chart_day),
                    created_at__lt=day_start(chart_day + timedelta(days=1)),
                ),
            )
            for index, chart_day in enumerate(days_in_period)
        }
    )
    revenue_by_day = {
        chart_day: daily_totals.get(f"day_{index}") or Decimal("0.00")
        for index, chart_day in enumerate(days_in_period)
    }
    max_daily_revenue = max(revenue_by_day.values(), default=Decimal("0.00"))
    weekday_labels = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")
    chart_points = []
    for chart_day in days_in_period:
        amount = revenue_by_day[chart_day]
        if period_days == 1:
            label = "Hôm nay"
        elif period_days <= 7:
            label = weekday_labels[chart_day.weekday()]
        else:
            label = str(chart_day.day) if chart_day.day == 1 or chart_day.day % 5 == 0 else ""
        height = round(float(amount / max_daily_revenue * 100), 1) if max_daily_revenue else 0
        chart_points.append(
            {"day": chart_day, "label": label, "amount": amount, "height": height}
        )

    period_status_counts = []
    for value, label in Order.Status.choices:
        count = period_orders.filter(status=value).count()
        period_status_counts.append(
            {
                "label": label,
                "value": value,
                "count": count,
                "percentage": round(count * 100 / period_order_count, 1) if period_order_count else 0,
            }
        )
    payment_labels = dict(Order.PaymentMethod.choices)
    payment_rows = list(
        period_active_orders.values("payment_method")
        .annotate(order_count=Count("pk"), order_value=Sum("total"))
        .order_by("payment_method")
    )
    period_payment_total = sum(
        (row["order_value"] or Decimal("0.00") for row in payment_rows),
        Decimal("0.00"),
    )
    period_payment_summaries = [
        {
            **row,
            "label": payment_labels.get(row["payment_method"], row["payment_method"]),
            "percentage": (
                round(row["order_value"] * 100 / period_payment_total, 1)
                if period_payment_total
                else 0
            ),
        }
        for row in payment_rows
    ]
    popular_products = (
        OrderItem.objects.filter(
            order__status=Order.Status.DELIVERED,
            order__created_at__gte=day_start(period_start),
            order__created_at__lt=day_start(today + timedelta(days=1)),
        )
        .values("product_name")
        .annotate(quantity=Sum("quantity"))
        .order_by("-quantity", "product_name")[:5]
    )
    unavailable_products = Product.objects.filter(is_available=False).order_by("name")[:3]
    unavailable_product_count = Product.objects.filter(is_available=False).count()
    period_pending_count = period_orders.filter(status=Order.Status.PENDING).count()
    due_today_count = (
        orders.filter(delivery_date=today)
        .exclude(status__in=[Order.Status.DELIVERED, Order.Status.CANCELLED])
        .count()
    )
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="fitmeal-orders-{today:%Y%m%d}-{selected_range}.csv"'
        )
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["Mã đơn", "Ngày đặt", "Trạng thái", "Thanh toán", "Tổng tiền"])
        for order in period_orders.order_by("-created_at").iterator():
            writer.writerow(
                [
                    order.order_number,
                    timezone.localtime(order.created_at).strftime("%d/%m/%Y %H:%M"),
                    order.get_status_display(),
                    order.get_payment_method_display(),
                    order.total,
                ]
            )
        return response

    active_section = request.GET.get("section", "overview")
    sections = {
        "overview",
        "orders",
        "employees",
        "products",
        "customers",
        "payments",
        "shipping",
        "security",
        "operations",
    }
    if active_section not in sections:
        active_section = "overview"

    page_obj = None
    order_rows = []
    selected_order = None
    selected_order_form = None
    status_tabs = []
    orders_date_range = "today"
    selected_status = "all"
    payment_filter = "all"
    payment_methods = (
        (
            Order.PaymentMethod.BANK_TRANSFER,
            Order.PaymentMethod.BANK_TRANSFER.label,
        ),
    )
    order_search = ""
    orders_date_range_label = "Hôm nay"
    order_action_query = ""
    product_rows = []
    customer_rows = []
    employee_form = None
    employee_credentials = None
    employee_rows = []
    employee_status = 200
    if active_section == "employees":
        from apps.accounts.forms import EmployeeCreationForm

        if request.method == "POST":
            employee_form = EmployeeCreationForm(request.POST)
            if employee_form.is_valid():
                with transaction.atomic():
                    employee, temporary_password = employee_form.save()
                employee_credentials = {
                    "email": employee.email,
                    "password": temporary_password,
                }
                employee_form = EmployeeCreationForm()
            else:
                employee_status = 400
        else:
            employee_form = EmployeeCreationForm()
        employee_rows = get_user_model().objects.filter(is_staff=True).order_by(
            "first_name", "last_name", "pk"
        )
    if active_section == "orders":
        date_ranges = {
            "today": ("Hôm nay", 1),
            "7d": ("7 ngày", 7),
            "30d": ("30 ngày", 30),
            "all": ("Tất cả thời gian", None),
        }
        orders_date_range = request.GET.get("date_range", "today")
        if orders_date_range not in date_ranges:
            orders_date_range = "today"
        orders_date_range_label, order_range_days = date_ranges[orders_date_range]
        date_orders = orders
        if order_range_days:
            date_orders = date_orders.filter(
                created_at__gte=day_start(today - timedelta(days=order_range_days - 1)),
                created_at__lt=day_start(today + timedelta(days=1)),
            )

        status_groups = (
            ("all", "Tất cả", ()),
            ("pending", "Chờ xác nhận", (Order.Status.PENDING,)),
            (
                "preparing",
                "Đang xử lý",
                (
                    Order.Status.CONFIRMED,
                    Order.Status.PREPARING,
                    Order.Status.PACKING,
                    Order.Status.READY,
                    Order.Status.SHIPPED,
                ),
            ),
            (
                "delivering",
                "Đang giao / chờ xác nhận",
                (
                    Order.Status.DELIVERING,
                    Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
                ),
            ),
            ("delivery_issues", "Khiếu nại giao hàng", (Order.Status.DELIVERY_ISSUE,)),
            ("delivered", "Hoàn tất", (Order.Status.DELIVERED,)),
            ("cancelled", "Đã hủy", (Order.Status.CANCELLED,)),
        )
        orders_by_tab = {
            tab_value: tab_statuses
            for tab_value, _tab_label, tab_statuses in status_groups
        }
        selected_status = request.GET.get("status", "all")
        if selected_status not in orders_by_tab:
            selected_status = "all"
        for tab_value, tab_label, tab_statuses in status_groups:
            tab_orders = date_orders.filter(status__in=tab_statuses) if tab_statuses else date_orders
            status_tabs.append(
                {"value": tab_value, "label": tab_label, "count": tab_orders.count()}
            )

        filtered_orders = date_orders
        selected_statuses = orders_by_tab[selected_status]
        if selected_statuses:
            filtered_orders = filtered_orders.filter(status__in=selected_statuses)
        payment_method_values = dict(payment_methods)
        payment_filter = request.GET.get("payment", "all")
        if payment_filter not in ("all", *payment_method_values.keys()):
            payment_filter = "all"
        if payment_filter != "all":
            filtered_orders = filtered_orders.filter(payment_method=payment_filter)
        order_search = request.GET.get("q", "").strip()[:100]
        if order_search:
            filtered_orders = filtered_orders.filter(
                Q(order_number__icontains=order_search)
                | Q(customer_name__icontains=order_search)
                | Q(customer_phone__icontains=order_search)
            )

        if request.GET.get("export") == "orders":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                f'attachment; filename="fitmeal-orders-{today:%Y%m%d}-{orders_date_range}.csv"'
            )
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(
                ["Mã đơn", "Ngày đặt", "Khách hàng", "Điện thoại", "Tổng tiền", "Thanh toán", "Trạng thái"]
            )
            for order in filtered_orders.order_by("-created_at", "-pk").iterator():
                writer.writerow(
                    [
                        order.order_number,
                        timezone.localtime(order.created_at).strftime("%d/%m/%Y %H:%M"),
                        _safe_csv_value(order.customer_name),
                        _safe_csv_value(order.customer_phone),
                        order.total,
                        order.get_payment_method_display(),
                        order.get_status_display(),
                    ]
                )
            return response

        page_obj = Paginator(
            filtered_orders.order_by("-created_at", "-pk")
            .select_related("customer")
            .prefetch_related("items"),
            25,
        ).get_page(request.GET.get("page"))
        order_rows = page_obj.object_list
        selected_order_id = request.GET.get("order", "")
        if selected_order_id.isdecimal():
            selected_order = (
                filtered_orders.select_related("customer")
                .prefetch_related("items")
                .filter(pk=int(selected_order_id))
                .first()
            )
        if selected_order is None and order_rows:
            selected_order = order_rows[0]
        if selected_order:
            selected_order.has_open_cancellation_request = OrderCancellationRequest.objects.filter(
                order=selected_order,
                status__in=OPEN_CANCELLATION_STATUSES,
            ).exists()
            selected_order_form = OrderStatusUpdateForm(instance=selected_order)
            order_action_query = urlencode(
                {
                    "section": "orders",
                    "date_range": orders_date_range,
                    "status": selected_status,
                    "payment": payment_filter,
                    "q": order_search,
                    "order": selected_order.pk,
                }
            )
    elif active_section == "products":
        page_obj = Paginator(Product.objects.all(), 20).get_page(request.GET.get("page"))
        product_rows = [
            {"product": product, "form": ProductQuickEditForm(instance=product)}
            for product in page_obj.object_list
        ]
    elif active_section == "customers":
        customer_queryset = (
            get_user_model()
            .objects.filter(is_staff=False)
            .annotate(order_count=Count("orders"), order_value=Sum("orders__total"))
            .order_by("first_name", "last_name", "pk")
        )
        page_obj = Paginator(customer_queryset, 25).get_page(request.GET.get("page"))
        customer_rows = page_obj.object_list

    recent_orders = orders.select_related("customer").prefetch_related("items")[:8]
    status_counts = [
        {"label": label, "value": value, "count": orders.filter(status=value).count()}
        for value, label in Order.Status.choices
    ]
    payment_summaries = orders.values("payment_method").annotate(
        order_count=Count("pk"),
        order_value=Sum("total"),
    )
    payment_transaction_summaries = []
    recent_payment_transactions = []
    if active_section == "payments":
        status_labels = dict(PaymentTransaction.Status.choices)
        payment_transaction_summaries = [
            {
                **row,
                "label": status_labels[row["status"]],
            }
            for row in PaymentTransaction.objects.values("status")
            .annotate(
                transaction_count=Count("pk"),
                transaction_value=Sum("amount"),
            )
            .order_by("status")
        ]
        recent_payment_transactions = (
            PaymentTransaction.objects.select_related("order")
            .order_by("-created_at", "-pk")[:20]
        )
    shipping_orders = orders.filter(
        status__in=[
            Order.Status.CONFIRMED,
            Order.Status.PREPARING,
            Order.Status.PACKING,
            Order.Status.READY,
            Order.Status.SHIPPED,
            Order.Status.DELIVERING,
            Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
        ]
    ).select_related("customer").order_by("-created_at")[:50]
    titles = {
        "overview": "Tổng quan",
        "orders": "Đơn hàng",
        "employees": "Nhân viên & phân quyền",
        "products": "Sản phẩm",
        "customers": "Khách hàng",
        "payments": "Thanh toán",
        "shipping": "Vận chuyển",
        "security": "Bảo mật",
        "operations": "Vận hành hệ thống",
    }
    system_context = {}
    if active_section == "security":
        system_context = get_security_dashboard_context(request)
    elif active_section == "operations":
        system_context = get_operations_dashboard_context()
    response = render(
        request,
        "orders/staff_dashboard.html",
        {
            "active_section": active_section,
            "section_title": titles[active_section],
            "page_obj": page_obj,
            "order_rows": order_rows,
            "selected_order": selected_order,
            "selected_order_form": selected_order_form,
            "status_tabs": status_tabs,
            "orders_date_range": orders_date_range,
            "orders_date_range_label": orders_date_range_label,
            "selected_status": selected_status,
            "payment_filter": payment_filter,
            "payment_methods": payment_methods,
            "order_search": order_search,
            "order_action_query": order_action_query,
            "product_rows": product_rows,
            "product_form": ProductCreateForm(),
            "customer_rows": customer_rows,
            "employee_rows": employee_rows,
            "employee_form": employee_form,
            "employee_credentials": employee_credentials,
            "staff_role_choices": get_user_model().StaffRole.choices,
            "recent_orders": recent_orders,
            "status_counts": status_counts,
            "payment_summaries": payment_summaries,
            "payment_transaction_summaries": payment_transaction_summaries,
            "recent_payment_transactions": recent_payment_transactions,
            "shipping_orders": shipping_orders,
            "order_count": orders.count(),
            "pending_count": orders.filter(status=Order.Status.PENDING).count(),
            "active_order_value": active_order_value,
            "completed_revenue": revenue,
            "outstanding_order_value": outstanding_order_value,
            "product_count": Product.objects.count(),
            "available_product_count": Product.objects.filter(is_available=True).count(),
            "customer_count": get_user_model().objects.filter(is_staff=False).count(),
            "guest_order_count": orders.filter(customer__isnull=True).count(),
            "selected_range": selected_range,
            "period_label": {
                "today": "Hôm nay",
                "7d": "7 ngày qua",
                "30d": "30 ngày qua",
            }[selected_range],
            "period_start": period_start,
            "period_days": period_days,
            "period_end": today,
            "period_pending_count": period_pending_count,
            "period_revenue": period_revenue,
            "previous_revenue": previous_revenue,
            "revenue_comparison": _period_comparison(period_revenue, previous_revenue),
            "period_order_count": period_order_count,
            "orders_comparison": _period_comparison(period_order_count, previous_order_count),
            "average_order_value": average_order_value,
            "previous_average_order_value": previous_average_order_value,
            "cancellation_rate": cancellation_rate,
            "canceled_count": canceled_count,
            "period_status_counts": period_status_counts,
            "period_payment_summaries": period_payment_summaries,
            "chart_points": chart_points,
            "max_daily_revenue": max_daily_revenue,
            "popular_products": popular_products,
            "unavailable_products": unavailable_products,
            "unavailable_product_count": unavailable_product_count,
            "due_today_count": due_today_count,
            **system_context,
        },
        status=employee_status,
    )
    if employee_credentials:
        response["Cache-Control"] = "no-store"
    return response


def _can_access_employee_workspace(user):
    user_model = get_user_model()
    return (
        user.is_authenticated
        and user.is_staff
        and not user.is_superuser
        and user.staff_role in {user_model.StaffRole.MANAGER, user_model.StaffRole.SALES}
    )


def _can_manage_catalog(user):
    user_model = get_user_model()
    return user.is_superuser or (
        user.is_authenticated
        and user.is_staff
        and user.staff_role == user_model.StaffRole.MANAGER
    )


def _catalog_products():
    sales_start = timezone.now() - timedelta(days=7)
    return Product.objects.annotate(
        sold_7d=Sum(
            "order_items__quantity",
            filter=Q(
                order_items__order__status=Order.Status.DELIVERED,
                order_items__order__created_at__gte=sales_start,
            ),
        )
    )


def _product_inventory_status(product):
    if not product.tracks_inventory:
        return "made-to-order"
    if product.stock_quantity is None:
        return "unknown"
    if product.stock_quantity == 0:
        return "out"
    if product.stock_quantity <= product.low_stock_threshold:
        return "low"
    return "available"


@login_required
def staff_dashboard(request):
    purge_expired_order_pii()
    if request.user.is_superuser:
        finalize_expired_delivery_confirmations()
        return admin_staff_dashboard(request)
    if not _can_access_employee_workspace(request.user):
        raise PermissionDenied
    finalize_expired_delivery_confirmations()
    return employee_workspace(request)


def employee_workspace(request):
    user = request.user
    if not _can_access_employee_workspace(user):
        raise PermissionDenied

    open_cancellation_for_order = OrderCancellationRequest.objects.filter(
        order_id=OuterRef("pk"),
        status__in=OPEN_CANCELLATION_STATUSES,
    )
    orders = Order.objects.annotate(
        has_open_cancellation_request=Exists(open_cancellation_for_order)
    )
    today = timezone.localdate()
    current_timezone = timezone.get_current_timezone()

    def day_start(day):
        return timezone.make_aware(datetime.combine(day, time.min), current_timezone)

    today_start = day_start(today)
    tomorrow_start = day_start(today + timedelta(days=1))
    today_orders = orders.filter(created_at__gte=today_start, created_at__lt=tomorrow_start)
    pending_orders = orders.filter(status=Order.Status.PENDING)
    preparing_orders = orders.filter(
        status__in=[
            Order.Status.CONFIRMED,
            Order.Status.PREPARING,
            Order.Status.PACKING,
            Order.Status.READY,
            Order.Status.SHIPPED,
        ]
    )
    delivering_orders = orders.filter(
        status__in=[
            Order.Status.DELIVERING,
            Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
        ]
    )
    query = request.GET.get("q", "").strip()[:100]
    is_manager = user.staff_role == user.StaffRole.MANAGER
    active_restock_requests = list(
        InventoryRestockRequest.objects.filter(
            status__in=[
                InventoryRestockRequest.Status.STAFF_ALERT,
                InventoryRestockRequest.Status.MANAGER_REVIEW,
            ]
        )
        .select_related("product", "requested_by")
        .order_by("status", "updated_at", "pk")
    )
    for restock_request in active_restock_requests:
        restock_request.can_fulfill = bool(
            restock_request.status == InventoryRestockRequest.Status.MANAGER_REVIEW
            and restock_request.product
            and restock_request.product.stock_quantity is not None
            and restock_request.product.stock_quantity
            >= restock_request.requested_quantity
        )
    manager_restock_requests = [
        restock_request
        for restock_request in active_restock_requests
        if restock_request.status == InventoryRestockRequest.Status.MANAGER_REVIEW
    ]
    pending_inventory_restock_count = sum(
        restock_request.status == InventoryRestockRequest.Status.MANAGER_REVIEW
        for restock_request in active_restock_requests
    ) if is_manager else 0
    active_section = request.GET.get("workspace", "work")
    allowed_sections = {"work", "orders", "customers", "menu", "profile"}
    if is_manager:
        allowed_sections.update({"inventory", "reports", "activity"})
    if active_section not in allowed_sections:
        active_section = "work"
    orders_view = request.GET.get("view", "orders")
    if not is_manager or orders_view not in {
        "orders",
        "cancellations",
        "delivery_failures",
        "delivery_issues",
        "customer_care",
    }:
        orders_view = "orders"
    pending_delivery_issues = DeliveryIssue.objects.filter(
        status=DeliveryIssue.Status.PENDING,
        order__status=Order.Status.DELIVERY_ISSUE,
    )

    page_obj = None
    cancellation_request_rows = []
    delivery_issue_rows = []
    selected_delivery_issue = None
    care_request_rows = []
    selected_care_request = None
    customer_rows = []
    menu_products = []
    product_rows = []
    selected_product = None
    selected_product_form = None
    price_history = []
    employee_menu_stats = {}
    product_filter = request.GET.get("filter", "all")
    allowed_product_filters = {
        "all",
        "selling",
        "paused",
        "low",
        "out",
        "fresh",
        "dry",
    }
    if product_filter not in allowed_product_filters:
        product_filter = "all"
    product_stats = (
        {
            "selling": Product.objects.filter(is_available=True).count(),
            "paused": Product.objects.filter(is_available=False).count(),
            "low": Product.objects.filter(
                category=Product.Category.DRY_GOODS,
                stock_quantity__gt=0,
                stock_quantity__lte=F("low_stock_threshold"),
            ).count(),
            "out": Product.objects.filter(
                category=Product.Category.DRY_GOODS,
                stock_quantity=0,
            ).count(),
            "unknown": Product.objects.filter(
                category=Product.Category.DRY_GOODS,
                stock_quantity__isnull=True,
            ).count(),
            "inventory_selling": Product.objects.filter(
                category=Product.Category.DRY_GOODS,
                is_available=True,
            ).count(),
            "inventory_paused": Product.objects.filter(
                category=Product.Category.DRY_GOODS,
                is_available=False,
            ).count(),
        }
        if is_manager
        else {
            "selling": 0,
            "paused": 0,
            "low": 0,
            "out": 0,
            "unknown": 0,
            "inventory_selling": 0,
            "inventory_paused": 0,
        }
    )
    if active_section == "orders":
        if is_manager and orders_view == "cancellations":
            cancellation_search = OrderCancellationRequest.objects.filter(
                status=OrderCancellationRequest.Status.MANAGER_REVIEW
            ).select_related(
                "order",
                "order__customer",
                "requested_by",
                "contacted_by",
            )
            if query:
                cancellation_search = cancellation_search.filter(
                    Q(reason__icontains=query)
                    | Q(contact_notes__icontains=query)
                    | Q(order__order_number__icontains=query)
                    | Q(order__customer_name__icontains=query)
                    | Q(order__customer_phone__icontains=query)
                )
            page_obj = Paginator(cancellation_search, 25).get_page(request.GET.get("page"))
            cancellation_request_rows = page_obj.object_list
        elif is_manager and orders_view in {"delivery_failures", "delivery_issues"}:
            delivery_issue_search = pending_delivery_issues.select_related(
                "order", "order__customer", "reported_by"
            ).prefetch_related("order__items")
            if orders_view == "delivery_failures":
                delivery_issue_search = delivery_issue_search.filter(
                    source=DeliveryIssue.Source.STAFF_DELIVERY
                )
            else:
                delivery_issue_search = delivery_issue_search.filter(
                    source=DeliveryIssue.Source.CUSTOMER
                )
            if query:
                delivery_issue_search = delivery_issue_search.filter(
                    Q(details__icontains=query)
                    | Q(order__order_number__icontains=query)
                    | Q(order__customer_name__icontains=query)
                    | Q(order__customer_phone__icontains=query)
                )
            page_obj = Paginator(delivery_issue_search, 25).get_page(
                request.GET.get("page")
            )
            delivery_issue_rows = page_obj.object_list
            selected_issue_id = request.GET.get("issue")
            selected_delivery_issue = next(
                (
                    issue
                    for issue in delivery_issue_rows
                    if str(issue.pk) == selected_issue_id
                ),
                None,
            )
            if selected_delivery_issue is None and delivery_issue_rows:
                selected_delivery_issue = delivery_issue_rows[0]
        elif is_manager and orders_view == "customer_care":
            care_request_search = OrderCareRequest.objects.filter(
                status=OrderCareRequest.Status.PENDING
            ).select_related(
                "order",
                "order__customer",
                "requested_by",
            ).prefetch_related("order__items")
            if query:
                care_request_search = care_request_search.filter(
                    Q(details__icontains=query)
                    | Q(order__order_number__icontains=query)
                    | Q(request_type__icontains=query)
                )
            page_obj = Paginator(care_request_search, 25).get_page(
                request.GET.get("page")
            )
            care_request_rows = page_obj.object_list
            selected_request_id = request.GET.get("care_request")
            selected_care_request = next(
                (
                    care_request
                    for care_request in care_request_rows
                    if str(care_request.pk) == selected_request_id
                ),
                None,
            )
            if selected_care_request is None and care_request_rows:
                selected_care_request = care_request_rows[0]
            if selected_care_request:
                selected_order = selected_care_request.order
                selected_care_request.pii_visible_in_window = (
                    selected_order.can_submit_customer_care_request()
                )
                if (
                    selected_care_request.pii_visible_in_window
                    and not selected_order.customer_pii_purged_at
                ):
                    _restore_order_pii_for_display(selected_order)
        else:
            order_search = orders.select_related("customer").prefetch_related("items")
            if query:
                order_search = order_search.filter(
                    Q(order_number__icontains=query)
                    | Q(customer_name__icontains=query)
                    | Q(customer_phone__icontains=query)
                )
            page_obj = Paginator(order_search.order_by("-created_at", "-pk"), 25).get_page(
                request.GET.get("page")
            )
    elif active_section == "customers":
        customer_search = (
            get_user_model()
            .objects.filter(is_staff=False)
            .annotate(
                order_count=Count("orders"),
                order_value=Sum("orders__total"),
            )
            .order_by("first_name", "last_name", "pk")
        )
        if query:
            customer_search = customer_search.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
                | Q(phone__icontains=query)
            )
        page_obj = Paginator(customer_search, 25).get_page(request.GET.get("page"))
        customer_rows = page_obj.object_list
    elif (active_section == "menu" and is_manager) or active_section == "inventory":
        catalog = _catalog_products().order_by("name", "pk")
        if active_section == "inventory":
            catalog = catalog.filter(category=Product.Category.DRY_GOODS)
        if query:
            catalog = catalog.filter(Q(name__icontains=query) | Q(sku__icontains=query))
        if active_section == "menu":
            if product_filter == "dry":
                catalog = catalog.filter(category=Product.Category.DRY_GOODS)
            elif product_filter == "fresh":
                catalog = catalog.exclude(category=Product.Category.DRY_GOODS)
            elif product_filter == "selling":
                catalog = catalog.filter(is_available=True)
            elif product_filter == "paused":
                catalog = catalog.filter(is_available=False)
            elif product_filter == "low":
                catalog = catalog.filter(
                    Q(
                        category=Product.Category.DRY_GOODS,
                        stock_quantity=0,
                    )
                    | Q(
                        category=Product.Category.DRY_GOODS,
                        stock_quantity__gt=0,
                        stock_quantity__lte=F("low_stock_threshold"),
                    )
                )
            elif product_filter == "out":
                catalog = catalog.filter(
                    category=Product.Category.DRY_GOODS,
                    stock_quantity=0,
                )
        elif product_filter == "low":
            catalog = catalog.filter(
                stock_quantity__gt=0,
                stock_quantity__lte=F("low_stock_threshold"),
            )
        elif product_filter == "out":
            catalog = catalog.filter(stock_quantity=0)
        page_obj = Paginator(catalog, 50).get_page(request.GET.get("page"))
        product_rows = [
            {
                "product": product,
                "sold_7d": product.sold_7d or 0,
                "inventory_status": _product_inventory_status(product),
            }
            for product in page_obj.object_list
        ]
        selected_product_id = request.GET.get("product", "")
        selected_product = next(
            (
                row["product"]
                for row in product_rows
                if str(row["product"].pk) == selected_product_id
            ),
            product_rows[0]["product"] if product_rows else None,
        )
        if selected_product:
            product_form_class = (
                ProductInventoryUpdateForm
                if active_section == "inventory"
                else ProductManagerUpdateForm
            )
            selected_product_form = product_form_class(
                instance=selected_product,
                auto_id="manager_edit_%s",
            )
            price_history = ProductActivity.objects.filter(
                product=selected_product,
                action__in=[
                    ProductActivity.Action.CREATED,
                    ProductActivity.Action.PRICE_CHANGED,
                ],
            )[:10]
    elif active_section == "menu":
        menu_catalog = Product.objects.order_by("category", "name")
        if query:
            menu_catalog = menu_catalog.filter(
                Q(name__icontains=query) | Q(sku__icontains=query)
            )
        if product_filter == "dry":
            menu_catalog = menu_catalog.filter(category=Product.Category.DRY_GOODS)
        elif product_filter == "fresh":
            menu_catalog = menu_catalog.exclude(category=Product.Category.DRY_GOODS)
        elif product_filter == "selling":
            menu_catalog = menu_catalog.filter(is_available=True)
        elif product_filter == "paused":
            menu_catalog = menu_catalog.filter(is_available=False)
        elif product_filter == "low":
            menu_catalog = menu_catalog.filter(
                category=Product.Category.DRY_GOODS
            ).filter(
                Q(stock_quantity=0)
                | Q(
                    stock_quantity__gt=0,
                    stock_quantity__lte=F("low_stock_threshold"),
                )
            )
        elif product_filter == "out":
            menu_catalog = menu_catalog.filter(
                category=Product.Category.DRY_GOODS,
                stock_quantity=0,
            )
        menu_products = menu_catalog
        employee_menu_stats = {
            "total": Product.objects.count(),
            "selling": Product.objects.filter(is_available=True).count(),
            "fresh": Product.objects.exclude(
                category=Product.Category.DRY_GOODS
            ).count(),
            "dry": Product.objects.filter(
                category=Product.Category.DRY_GOODS
            ).count(),
            "low_or_out": Product.objects.filter(
                category=Product.Category.DRY_GOODS
            ).filter(
                Q(stock_quantity=0)
                | Q(
                    stock_quantity__gt=0,
                    stock_quantity__lte=F("low_stock_threshold"),
                )
            ).count(),
            "paused": Product.objects.filter(is_available=False).count(),
        }

    report_range = request.GET.get("range", "7d")
    report_range_options = {
        "today": (1, "Hôm nay"),
        "7d": (7, "7 ngày gần nhất"),
        "30d": (30, "30 ngày gần nhất"),
    }
    if report_range not in {*report_range_options, "custom"}:
        report_range = "7d"
    report_period_days, report_period_label = report_range_options.get(
        report_range,
        (7, "Khoảng tùy chọn"),
    )
    report_end = today
    report_start = today - timedelta(days=report_period_days - 1)
    if report_range == "custom":
        try:
            custom_start = date.fromisoformat(request.GET.get("start", ""))
            custom_end = date.fromisoformat(request.GET.get("end", ""))
        except ValueError:
            report_range = "7d"
        else:
            custom_days = (custom_end - custom_start).days + 1
            if (
                custom_start <= custom_end <= today
                and custom_days <= 90
            ):
                report_start = custom_start
                report_end = custom_end
                report_period_days = custom_days
            else:
                report_range = "7d"
        if report_range == "7d":
            report_period_days, report_period_label = report_range_options["7d"]
            report_start = today - timedelta(days=report_period_days - 1)

    report_start_at = day_start(report_start)
    report_end_at = day_start(report_end + timedelta(days=1))
    report_chart_min_width = (
        (6 if report_range == "today" else report_period_days) * 52
    )
    report_previous_end = report_start - timedelta(days=1)
    report_previous_start = report_previous_end - timedelta(days=report_period_days - 1)
    report_order_count = 0
    report_completed_count = 0
    report_cancelled_count = 0
    report_revenue = Decimal("0.00")
    report_previous_revenue = Decimal("0.00")
    report_average_order_value = Decimal("0.00")
    report_completion_percentage = 0
    report_cancellation_percentage = 0
    report_cancellation_change = "Không có dữ liệu kỳ trước"
    report_cancellation_direction = "neutral"
    report_chart_points = []
    report_chart_peak = None
    report_chart_has_data = False
    report_category_rows = []
    report_delivery_rows = []
    report_payment_rows = []
    report_cancellation_reason_rows = []
    if active_section == "reports":
        report_orders = orders.filter(
            created_at__gte=report_start_at,
            created_at__lt=report_end_at,
        )
        report_completed_orders = report_orders.filter(status=Order.Status.DELIVERED)
        report_order_count = report_orders.count()
        report_completed_count = report_completed_orders.count()
        report_cancelled_orders = report_orders.filter(status=Order.Status.CANCELLED)
        report_cancelled_count = report_cancelled_orders.count()
        report_revenue = (
            report_completed_orders.aggregate(total=Sum("subtotal"))["total"]
            or Decimal("0.00")
        )
        previous_report_orders = orders.filter(
            created_at__gte=day_start(report_previous_start),
            created_at__lt=day_start(report_previous_end + timedelta(days=1)),
        )
        report_previous_revenue = (
            previous_report_orders.filter(status=Order.Status.DELIVERED)
            .aggregate(total=Sum("subtotal"))["total"]
            or Decimal("0.00")
        )
        report_previous_cancelled_count = previous_report_orders.filter(
            status=Order.Status.CANCELLED
        ).count()
        report_previous_order_count = previous_report_orders.count()
        report_average_order_value = (
            report_revenue / report_completed_count if report_completed_count else Decimal("0.00")
        )
        report_completion_percentage = round(
            report_completed_count * 100 / report_order_count if report_order_count else 0
        )
        report_cancellation_percentage = (
            report_cancelled_count * 100 / report_order_count if report_order_count else 0
        )
        previous_cancellation_percentage = (
            report_previous_cancelled_count * 100 / report_previous_order_count
            if report_previous_order_count
            else 0
        )
        cancellation_change = round(
            report_cancellation_percentage - previous_cancellation_percentage,
            1,
        )
        report_cancellation_direction = "good" if cancellation_change <= 0 else "bad"
        if cancellation_change == 0:
            report_cancellation_change = "Không đổi so với kỳ trước"
        else:
            arrow = "▼" if cancellation_change < 0 else "▲"
            report_cancellation_change = (
                f"{arrow} {abs(cancellation_change):.1f} điểm so với kỳ trước"
            )

        weekday_labels = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")
        chart_values = []
        if report_range == "today":
            hour_slots = ((6, 9), (9, 12), (12, 15), (15, 18), (18, 21))
            hourly_report_orders = report_orders.exclude(
                status=Order.Status.CANCELLED
            )
            hourly_totals = hourly_report_orders.aggregate(
                **{
                    f"slot_{index}": Sum(
                        "subtotal",
                        filter=Q(
                            created_at__gte=today_start + timedelta(hours=start_hour),
                            created_at__lt=today_start + timedelta(hours=end_hour),
                        ),
                    )
                    for index, (start_hour, end_hour) in enumerate(hour_slots)
                }
            )
            for index, (start_hour, end_hour) in enumerate(hour_slots):
                slot_label = f"{start_hour}–{end_hour}h"
                chart_values.append(
                    {
                        "day": today,
                        "label": slot_label,
                        "tooltip": slot_label,
                        "amount": hourly_totals.get(f"slot_{index}")
                        or Decimal("0.00"),
                    }
                )
            outside_hours_total = hourly_report_orders.aggregate(
                amount=Sum(
                    "subtotal",
                    filter=Q(
                        created_at__lt=today_start + timedelta(hours=6)
                    )
                    | Q(
                        created_at__gte=today_start + timedelta(hours=21)
                    ),
                )
            )["amount"] or Decimal("0.00")
            if outside_hours_total:
                chart_values.append(
                    {
                        "day": today,
                        "label": "Ngoài giờ",
                        "tooltip": "Ngoài khung 6–21h",
                        "amount": outside_hours_total,
                    }
                )
        else:
            daily_totals = report_completed_orders.aggregate(
                **{
                    f"day_{day_offset}": Sum(
                        "subtotal",
                        filter=Q(
                            created_at__gte=day_start(
                                report_start + timedelta(days=day_offset)
                            ),
                            created_at__lt=day_start(
                                report_start + timedelta(days=day_offset + 1)
                            ),
                        ),
                    )
                    for day_offset in range(report_period_days)
                }
            )
            for day_offset in range(report_period_days):
                chart_day = report_start + timedelta(days=day_offset)
                day_label = (
                    f"{weekday_labels[chart_day.weekday()]} {chart_day:%d/%m}"
                    if report_period_days <= 7
                    else chart_day.strftime("%d/%m")
                    if chart_day == report_start
                    or chart_day == report_end
                    or chart_day.day % 5 == 0
                    else ""
                )
                chart_values.append(
                    {
                        "day": chart_day,
                        "label": day_label,
                        "tooltip": chart_day.strftime("%d/%m/%Y"),
                        "amount": daily_totals.get(f"day_{day_offset}")
                        or Decimal("0.00"),
                    }
                )

        max_chart_revenue = max(
            (point["amount"] for point in chart_values),
            default=Decimal("0.00"),
        )
        chart_track_height = 160
        for point in chart_values:
            amount = point["amount"]
            height_percentage = (
                float(amount / max_chart_revenue * 100)
                if max_chart_revenue
                else 0
            )
            height_px = (
                max(3, round(height_percentage * chart_track_height / 100))
                if amount
                else 0
            )
            report_chart_points.append(
                {
                    **point,
                    "amount": amount,
                    "amount_display": _format_vnd(amount),
                    "height": round(height_percentage, 1),
                    "height_px": height_px,
                    "label_bottom": (
                        height_px + 29 if amount else 0
                    ),
                }
            )
        report_chart_peak = max(
            report_chart_points,
            key=lambda point: point["amount"],
            default=None,
        )
        report_chart_has_data = any(
            point["amount"] for point in report_chart_points
        )

        item_revenue_by_category = {
            row["product_category"]: row["amount"] or Decimal("0.00")
            for row in OrderItem.objects.filter(
                order__in=report_completed_orders
            )
            .values("product_category")
            .annotate(amount=Sum("line_total"))
        }
        dry_goods_revenue = item_revenue_by_category.pop(
            Product.Category.DRY_GOODS,
            Decimal("0.00"),
        )
        fresh_categories = set(Product.Category.values) - {Product.Category.DRY_GOODS}
        fresh_revenue = sum(
            (
                amount
                for category, amount in item_revenue_by_category.items()
                if category in fresh_categories
            ),
            Decimal("0.00"),
        )
        unknown_category_revenue = sum(
            (
                amount
                for category, amount in item_revenue_by_category.items()
                if category not in fresh_categories
            ),
            Decimal("0.00"),
        )
        report_category_total = dry_goods_revenue + fresh_revenue + unknown_category_revenue
        report_category_rows = [
            {
                "label": "Đồ tươi (chỉ TP.HCM)",
                "amount": fresh_revenue,
                "amount_display": _format_vnd(fresh_revenue),
                "percentage": (
                    round(fresh_revenue * 100 / report_category_total)
                    if report_category_total
                    else 0
                ),
                "color": "green",
            },
            {
                "label": "Đồ khô (toàn quốc)",
                "amount": dry_goods_revenue,
                "amount_display": _format_vnd(dry_goods_revenue),
                "percentage": (
                    round(dry_goods_revenue * 100 / report_category_total)
                    if report_category_total
                    else 0
                ),
                "color": "blue",
            },
        ]
        if unknown_category_revenue:
            report_category_rows.append(
                {
                    "label": "Chưa phân loại",
                    "amount": unknown_category_revenue,
                    "amount_display": _format_vnd(unknown_category_revenue),
                    "percentage": round(
                        unknown_category_revenue * 100 / report_category_total
                    ),
                    "color": "gray",
                }
            )

        delivery_revenue = {
            row["delivery_region"]: row["amount"] or Decimal("0.00")
            for row in report_completed_orders.values("delivery_region")
            .annotate(amount=Sum("subtotal"))
        }
        report_delivery_rows = [
            {
                "label": label,
                "amount_display": _format_vnd(delivery_revenue.get(value, Decimal("0.00"))),
                "percentage": (
                    round(delivery_revenue.get(value, Decimal("0.00")) * 100 / report_revenue)
                    if report_revenue
                    else 0
                ),
                "color": color,
            }
            for value, label, color in (
                (Order.DeliveryRegion.HO_CHI_MINH_CITY, "TP. Hồ Chí Minh", "green"),
                (Order.DeliveryRegion.OTHER_PROVINCES, "Các tỉnh khác", "blue"),
            )
        ]
        unknown_delivery_revenue = delivery_revenue.get("", Decimal("0.00"))
        if unknown_delivery_revenue:
            report_delivery_rows.append(
                {
                    "label": "Chưa phân loại",
                    "amount_display": _format_vnd(unknown_delivery_revenue),
                    "percentage": round(unknown_delivery_revenue * 100 / report_revenue),
                    "color": "gray",
                }
            )

        payment_revenue = {
            row["payment_method"]: row["amount"] or Decimal("0.00")
            for row in report_completed_orders.values("payment_method")
            .annotate(amount=Sum("subtotal"))
        }
        report_payment_rows = [
            {
                "label": "COD" if value == Order.PaymentMethod.COD else label,
                "amount_display": _format_vnd(payment_revenue.get(value, Decimal("0.00"))),
                "percentage": (
                    round(payment_revenue.get(value, Decimal("0.00")) * 100 / report_revenue)
                    if report_revenue
                    else 0
                ),
                "color": "green" if index == 0 else "blue",
            }
            for index, (value, label) in enumerate(Order.PaymentMethod.choices)
        ]

        cancellation_labels = dict(Order.CancellationReasonCategory.choices)
        reason_counts = list(
            report_cancelled_orders.values("cancellation_reason_category")
            .annotate(count=Count("pk"))
            .order_by("-count", "cancellation_reason_category")
        )
        max_reason_count = max((row["count"] for row in reason_counts), default=0)
        report_cancellation_reason_rows = [
            {
                "label": cancellation_labels.get(
                    row["cancellation_reason_category"],
                    "Chưa phân loại",
                )
                if row["cancellation_reason_category"]
                else "Chưa phân loại",
                "count": row["count"],
                "percentage": (
                    round(row["count"] * 100 / max_reason_count)
                    if max_reason_count
                    else 0
                ),
            }
            for row in reason_counts
        ]

        if request.GET.get("export") == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = (
                f'attachment; filename="fitmeal-revenue-{report_start:%Y%m%d}-{report_end:%Y%m%d}.csv"'
            )
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(["BÁO CÁO DOANH THU", report_period_label])
            writer.writerow(["Từ ngày", report_start.strftime("%d/%m/%Y")])
            writer.writerow(["Đến ngày", report_end.strftime("%d/%m/%Y")])
            writer.writerow(["Doanh thu hàng hóa", _format_vnd(report_revenue)])
            writer.writerow(["Đơn hoàn tất", f"{report_completed_count} / {report_order_count}"])
            writer.writerow(["Giá trị trung bình mỗi đơn", _format_vnd(report_average_order_value)])
            writer.writerow(["Tỷ lệ hủy", f"{report_cancellation_percentage:.1f}%"])
            writer.writerow([])
            if report_range == "today":
                writer.writerow(["Doanh thu theo khung giờ"])
                writer.writerow(["Khung giờ", "Doanh thu"])
                writer.writerows(
                    [
                        [point["label"], _format_vnd(point["amount"])]
                        for point in report_chart_points
                    ]
                )
            else:
                writer.writerow(["Doanh thu theo ngày"])
                writer.writerow(["Ngày", "Doanh thu"])
                writer.writerows(
                    [
                        [
                            point["day"].strftime("%d/%m/%Y"),
                            _format_vnd(point["amount"]),
                        ]
                        for point in report_chart_points
                    ]
                )
            writer.writerow([])
            writer.writerow(["Doanh thu theo khu vực"])
            writer.writerow(["Khu vực", "Doanh thu", "Tỷ trọng"])
            writer.writerows(
                [
                    [row["label"], row["amount_display"], f'{row["percentage"]}%']
                    for row in report_delivery_rows
                ]
            )
            writer.writerow([])
            writer.writerow(["Doanh thu theo nhóm món"])
            writer.writerow(["Nhóm món", "Doanh thu", "Tỷ trọng"])
            writer.writerows(
                [
                    [row["label"], row["amount_display"], f'{row["percentage"]}%']
                    for row in report_category_rows
                ]
            )
            writer.writerow([])
            writer.writerow(["Doanh thu theo thanh toán"])
            writer.writerow(["Phương thức", "Doanh thu", "Tỷ trọng"])
            writer.writerows(
                [
                    [row["label"], row["amount_display"], f'{row["percentage"]}%']
                    for row in report_payment_rows
                ]
            )
            writer.writerow([])
            writer.writerow(["Lý do hủy"])
            writer.writerow(["Lý do", "Số đơn"])
            writer.writerows(
                [[row["label"], row["count"]] for row in report_cancellation_reason_rows]
            )
            return response
    product_activity = (
        ProductActivity.objects.select_related("actor")
        .order_by("-created_at", "-pk")[:100]
    )
    contact_cancellation_requests = (
        OrderCancellationRequest.objects.filter(
            status=OrderCancellationRequest.Status.CONTACT_PENDING
        )
        .select_related("order", "order__customer", "requested_by")
        .order_by("requested_at", "pk")
    )
    pending_cancellation_count = (
        OrderCancellationRequest.objects.filter(
            status=OrderCancellationRequest.Status.MANAGER_REVIEW
        ).count()
        if is_manager
        else 0
    )
    pending_delivery_failure_count = (
        pending_delivery_issues.filter(
            source=DeliveryIssue.Source.STAFF_DELIVERY
        ).count()
        if is_manager
        else 0
    )
    pending_customer_complaint_count = (
        pending_delivery_issues.filter(
            source=DeliveryIssue.Source.CUSTOMER
        ).count()
        if is_manager
        else 0
    )
    pending_customer_care_count = (
        OrderCareRequest.objects.filter(status=OrderCareRequest.Status.PENDING).count()
        if is_manager
        else 0
    )

    section_titles = {
        "work": "Ca làm hôm nay",
        "orders": "Đơn hàng & khiếu nại",
        "customers": "Khách hàng",
        "menu": "Thực đơn & giá" if is_manager else "Thực đơn",
        "inventory": "Kho hàng",
        "reports": "Báo cáo doanh thu",
        "activity": "Nhật ký hoạt động",
        "profile": "Hồ sơ của tôi",
    }
    return render(
        request,
        "orders/employee_workspace.html",
        {
            "active_workspace": active_section,
            "workspace_title": section_titles[active_section],
            "employee_role": user.get_staff_role_display(),
            "is_manager": is_manager,
            "can_cancel_orders": is_manager,
            "can_request_cancellations": True,
            "contact_cancellation_requests": contact_cancellation_requests,
            "contact_cancellation_count": OrderCancellationRequest.objects.filter(
                status=OrderCancellationRequest.Status.CONTACT_PENDING
            ).count(),
            "pending_cancellation_count": pending_cancellation_count,
            "pending_delivery_failure_count": pending_delivery_failure_count,
            "pending_customer_complaint_count": pending_customer_complaint_count,
            "pending_customer_care_count": pending_customer_care_count,
            "today_order_count": today_orders.count(),
            "pending_count": pending_orders.count(),
            "preparing_count": preparing_orders.count(),
            "delivering_count": delivering_orders.count(),
            "completed_today_count": orders.filter(
                status=Order.Status.DELIVERED,
                updated_at__gte=today_start,
                updated_at__lt=tomorrow_start,
            ).count(),
            "pending_orders": pending_orders.select_related("customer")
            .prefetch_related("items")
            .order_by("created_at", "pk")[:60],
            "preparing_orders": preparing_orders.select_related("customer")
            .prefetch_related("items")
            .order_by("created_at", "pk")[:60],
            "delivering_orders": delivering_orders.select_related("customer")
            .prefetch_related("items")
            .order_by("created_at", "pk")[:60],
            "page_obj": page_obj,
            "orders_view": orders_view,
            "cancellation_request_rows": cancellation_request_rows,
            "delivery_issue_rows": delivery_issue_rows,
            "selected_delivery_issue": selected_delivery_issue,
            "care_request_rows": care_request_rows,
            "selected_care_request": selected_care_request,
            "customer_rows": customer_rows,
            "menu_products": menu_products,
            "product_rows": product_rows,
            "selected_product": selected_product,
            "selected_product_form": selected_product_form,
            "price_history": price_history,
            "product_filter": product_filter,
            "employee_menu_stats": employee_menu_stats,
            "product_stats": product_stats,
            "inventory_restock_requests": active_restock_requests,
            "manager_restock_requests": manager_restock_requests,
            "inventory_restock_alert_count": len(active_restock_requests),
            "pending_inventory_restock_count": pending_inventory_restock_count,
            "product_create_form": ProductCreateForm(auto_id="manager_create_%s"),
            "report_order_count": report_order_count,
            "report_completed_count": report_completed_count,
            "report_cancelled_count": report_cancelled_count,
            "report_revenue": report_revenue,
            "report_revenue_display": _format_vnd(report_revenue),
            "report_previous_revenue": report_previous_revenue,
            "report_previous_revenue_display": _format_vnd(report_previous_revenue),
            "report_revenue_comparison": _period_comparison(
                report_revenue,
                report_previous_revenue,
            ),
            "report_average_order_value": report_average_order_value,
            "report_average_order_value_display": _format_vnd(report_average_order_value),
            "report_completion_percentage": report_completion_percentage,
            "report_cancellation_percentage": report_cancellation_percentage,
            "report_cancellation_change": report_cancellation_change,
            "report_cancellation_direction": report_cancellation_direction,
            "report_chart_points": report_chart_points,
            "report_chart_peak": report_chart_peak,
            "report_chart_has_data": report_chart_has_data,
            "report_chart_min_width": report_chart_min_width,
            "report_category_rows": report_category_rows,
            "report_delivery_rows": report_delivery_rows,
            "report_payment_rows": report_payment_rows,
            "report_cancellation_reason_rows": report_cancellation_reason_rows,
            "report_range": report_range,
            "report_period_label": report_period_label,
            "report_period_days": report_period_days,
            "report_previous_start": report_previous_start,
            "report_previous_end": report_previous_end,
            "product_activity": product_activity,
            "report_start": report_start,
            "report_end": report_end,
            "query": query,
        },
    )


@login_required
@require_POST
def staff_update_order_status(request, order_id):
    if not request.user.is_superuser and not _can_access_employee_workspace(request.user):
        raise PermissionDenied

    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
        current_status = order.status
        form = OrderStatusUpdateForm(request.POST, instance=order)
        if form.is_valid():
            next_status = form.cleaned_data["status"]
            has_open_cancellation = OrderCancellationRequest.objects.filter(
                order=order,
                status__in=OPEN_CANCELLATION_STATUSES,
            ).exists()
            if has_open_cancellation:
                messages.error(
                    request,
                    "Hãy xử lý yêu cầu hủy đang mở trước khi cập nhật tiến độ đơn.",
                )
            elif (
                order.payment_method
                in {
                    Order.PaymentMethod.BANK_TRANSFER,
                    Order.PaymentMethod.VNPAY,
                }
                and not PaymentTransaction.objects.filter(
                    order=order,
                    status=PaymentTransaction.Status.PAID,
                ).exists()
            ):
                messages.error(
                    request,
                    "Chỉ có thể xử lý đơn thanh toán trực tuyến sau khi giao dịch được xác nhận.",
                )
            elif next_status in {
                Order.Status.PREPARING,
                Order.Status.PACKING,
            } and order.items.filter(
                product_category=Product.Category.DRY_GOODS,
                inventory_deducted=False,
            ).exists():
                messages.error(
                    request,
                    "Đơn đã được ghi nhận nhưng đang chờ bổ sung hàng; chưa thể chuẩn bị hoặc đóng gói.",
                )
            elif current_status in {
                Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
                Order.Status.DELIVERY_ISSUE,
            }:
                messages.error(
                    request,
                    "Đơn đang chờ phản hồi hoặc xử lý khiếu nại; không thể sửa trạng thái thủ công.",
                )
            elif next_status == Order.Status.AWAITING_CUSTOMER_CONFIRMATION:
                if current_status != Order.Status.DELIVERING:
                    messages.error(
                        request,
                        "Chỉ có thể chờ khách xác nhận sau khi đơn đang được giao.",
                    )
                else:
                    begin_customer_delivery_confirmation(order)
                    messages.success(
                        request,
                        f"Đã ghi nhận giao đơn {order.order_number}; chờ khách xác nhận trong 3 phút.",
                    )
            elif next_status == Order.Status.DELIVERY_ISSUE:
                if current_status != Order.Status.DELIVERING:
                    messages.error(
                        request,
                        "Chỉ có thể ghi nhận không liên lạc được khi đơn đang giao.",
                    )
                else:
                    DeliveryIssue.objects.create(
                        order=order,
                        source=DeliveryIssue.Source.STAFF_DELIVERY,
                        details="Không liên lạc được với khách khi giao hàng.",
                        reported_by=request.user,
                    )
                    order.status = Order.Status.DELIVERY_ISSUE
                    order.save(update_fields=["status", "updated_at"])
                    messages.success(
                        request,
                        "Đã ghi nhận giao hàng không thành công do không liên lạc được với khách.",
                    )
            elif next_status == Order.Status.DELIVERED:
                messages.error(
                    request,
                    "Trạng thái này chỉ được cập nhật theo phản hồi của khách hoặc Quản lý.",
                )
            elif request.user.is_superuser:
                form.save()
                messages.success(request, f"Đã cập nhật trạng thái đơn {order.order_number}.")
            else:
                allowed_transitions = {
                    Order.Status.PENDING: {Order.Status.CONFIRMED},
                }
                if order.is_dry_goods_order:
                    allowed_transitions.update(
                        {
                            Order.Status.CONFIRMED: {Order.Status.PACKING},
                            Order.Status.PACKING: {Order.Status.SHIPPED},
                            Order.Status.SHIPPED: {Order.Status.DELIVERING},
                            Order.Status.DELIVERING: {
                                Order.Status.AWAITING_CUSTOMER_CONFIRMATION
                            },
                        }
                    )
                else:
                    allowed_transitions.update(
                        {
                            Order.Status.CONFIRMED: {Order.Status.PREPARING},
                            Order.Status.PREPARING: {Order.Status.READY},
                            Order.Status.READY: {Order.Status.DELIVERING},
                            Order.Status.DELIVERING: {
                                Order.Status.AWAITING_CUSTOMER_CONFIRMATION
                            },
                        }
                    )
                allowed_statuses = allowed_transitions.get(current_status, set())
                if next_status not in allowed_statuses:
                    messages.error(request, "Vai trò của bạn không được phép thực hiện trạng thái này.")
                else:
                    form.save()
                    messages.success(
                        request,
                        f"Đã cập nhật trạng thái đơn {order.order_number}.",
                    )
        else:
            messages.error(request, "Trạng thái đơn hàng không hợp lệ.")
    if not request.user.is_superuser:
        workspace = request.GET.get("workspace", "work")
        if workspace not in {"work", "orders"}:
            workspace = "work"
        return redirect(f"{reverse('staff_orders:dashboard')}?workspace={workspace}#staff-workspace")

    redirect_params = {
        "section": "orders",
        "date_range": request.GET.get("date_range", "today"),
        "status": "all",
        "payment": request.GET.get("payment", "all"),
        "q": request.GET.get("q", ""),
        "order": order.pk,
    }
    return redirect(f"{reverse('staff_orders:dashboard')}?{urlencode(redirect_params)}#orders")


def _employee_workspace_redirect(request, workspace):
    if workspace not in {"work", "orders"}:
        workspace = "work"
    return redirect(f"{reverse('staff_orders:dashboard')}?workspace={workspace}#staff-workspace")


@login_required
@require_POST
def staff_request_order_cancellation(request, order_id):
    if not _can_access_employee_workspace(request.user):
        raise PermissionDenied
    workspace = request.GET.get("workspace", "work")
    form = CancellationReasonForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(form.errors.get("reason", [])) or "Lý do hủy không hợp lệ.")
        return _employee_workspace_redirect(request, workspace)

    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
        if order.status not in PRE_DELIVERY_STATUSES:
            messages.error(request, "Chỉ có thể yêu cầu hủy đơn chưa giao.")
            return _employee_workspace_redirect(request, workspace)
        if OrderCancellationRequest.objects.filter(
            order=order,
            status__in=OPEN_CANCELLATION_STATUSES,
        ).exists():
            messages.error(request, "Đơn này đã có yêu cầu hủy đang mở.")
            return _employee_workspace_redirect(request, workspace)
        OrderCancellationRequest.objects.create(
            order=order,
            source=OrderCancellationRequest.Source.STAFF,
            status=OrderCancellationRequest.Status.MANAGER_REVIEW,
            reason=form.cleaned_data["reason"],
            requested_by=request.user,
            contact_outcome=OrderCancellationRequest.ContactOutcome.NOT_REQUIRED,
        )
    messages.success(request, f"Đã chuyển yêu cầu hủy đơn {order.order_number} cho Quản lý.")
    return _employee_workspace_redirect(request, workspace)


@login_required
@require_POST
def staff_record_cancellation_contact(request, cancellation_id):
    if not _can_access_employee_workspace(request.user):
        raise PermissionDenied
    form = CancellationContactForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(form.errors.get("note", [])) or "Kết quả liên hệ không hợp lệ.")
        return _employee_workspace_redirect(request, "work")

    email_subject = ""
    email_body = ""
    with transaction.atomic():
        cancellation = get_object_or_404(
            OrderCancellationRequest.objects.select_for_update().select_related("order"),
            pk=cancellation_id,
        )
        if cancellation.status != OrderCancellationRequest.Status.CONTACT_PENDING:
            messages.error(request, "Yêu cầu này không còn chờ nhân viên liên hệ.")
            return _employee_workspace_redirect(request, "work")

        outcome = form.cleaned_data["outcome"]
        timestamp = timezone.localtime().strftime("%d/%m/%Y %H:%M")
        author = request.user.get_full_name() or request.user.username
        log_entry = f"{timestamp} · {author}: {form.cleaned_data['note']}"
        cancellation.contact_notes = "\n".join(
            value for value in (cancellation.contact_notes, log_entry) if value
        )[-4000:]
        cancellation.contact_outcome = outcome
        cancellation.contact_attempts += 1
        cancellation.contacted_by = request.user

        if outcome == OrderCancellationRequest.ContactOutcome.AGREED_TO_CONTINUE:
            cancellation.status = OrderCancellationRequest.Status.WITHDRAWN
            cancellation.resolved_by = request.user
            cancellation.resolved_at = timezone.now()
            email_subject = f"Đơn hàng {cancellation.order.order_number} tiếp tục được xử lý"
            email_body = (
                f"Bạn đã xác nhận tiếp tục nhận đơn {cancellation.order.order_number}.\n"
                "FitMeal sẽ tiếp tục chuẩn bị và giao đơn theo lịch đã hẹn."
            )
        elif outcome == OrderCancellationRequest.ContactOutcome.STILL_WANTS_CANCEL:
            cancellation.status = OrderCancellationRequest.Status.MANAGER_REVIEW
            email_subject = (
                f"Yêu cầu hủy đơn {cancellation.order.order_number} đang được quản lý xem xét"
            )
            email_body = (
                f"FitMeal đã ghi nhận xác nhận của bạn về yêu cầu hủy đơn "
                f"{cancellation.order.order_number}. Quản lý sẽ xem xét và gửi kết quả qua email."
            )
        elif outcome == OrderCancellationRequest.ContactOutcome.NO_ANSWER:
            if cancellation.contact_attempts >= 2:
                cancellation.status = OrderCancellationRequest.Status.MANAGER_REVIEW
                email_subject = (
                    f"Yêu cầu hủy đơn {cancellation.order.order_number} đang được quản lý xem xét"
                )
                email_body = (
                    f"FitMeal chưa liên hệ được với bạn sau {cancellation.contact_attempts} lần gọi. "
                    f"Yêu cầu hủy đơn {cancellation.order.order_number} đã được chuyển cho quản lý."
                )
        cancellation.save(
            update_fields=[
                "status",
                "contact_outcome",
                "contact_attempts",
                "contact_notes",
                "contacted_by",
                "resolved_by",
                "resolved_at",
                "updated_at",
            ]
        )

    if email_subject:
        sent = _send_cancellation_email(cancellation.order, email_subject, email_body)
        _cancellation_email_message(request, sent)
    if outcome == OrderCancellationRequest.ContactOutcome.AGREED_TO_CONTINUE:
        messages.success(request, "Đã ghi nhận khách tiếp tục nhận đơn.")
    elif outcome == OrderCancellationRequest.ContactOutcome.STILL_WANTS_CANCEL:
        messages.success(request, "Đã chuyển yêu cầu cho Quản lý duyệt.")
    elif cancellation.status == OrderCancellationRequest.Status.MANAGER_REVIEW:
        messages.success(request, "Đã gọi 2 lần không liên lạc được; yêu cầu đã chuyển cho Quản lý.")
    else:
        messages.info(request, "Đã ghi nhận lần gọi. Hãy liên hệ lại nếu khách chưa phản hồi.")
    return _employee_workspace_redirect(request, "work")


@login_required
@require_POST
def manager_resolve_cancellation(request, cancellation_id):
    if not _can_manage_catalog(request.user):
        raise PermissionDenied
    form = CancellationResolutionForm(request.POST)
    if not form.is_valid():
        errors = "; ".join(
            error for error_list in form.errors.values() for error in error_list
        )
        messages.error(request, errors or "Thông tin xử lý yêu cầu hủy không hợp lệ.")
        return redirect(f"{reverse('staff_orders:dashboard')}?workspace=orders&view=cancellations")

    email_subject = ""
    email_body = ""
    email_recipient = ""
    with transaction.atomic():
        order_id = get_object_or_404(
            OrderCancellationRequest.objects.filter(pk=cancellation_id).values_list(
                "order_id", flat=True
            )
        )
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
        email_recipient = order.customer_email
        cancellation = get_object_or_404(
            OrderCancellationRequest.objects.select_for_update().select_related("order"),
            pk=cancellation_id,
            order=order,
        )
        if cancellation.status != OrderCancellationRequest.Status.MANAGER_REVIEW:
            messages.error(request, "Yêu cầu này không còn chờ Quản lý xử lý.")
            return redirect(f"{reverse('staff_orders:dashboard')}?workspace=orders&view=cancellations")
        if form.cleaned_data["decision"] == "approve":
            if order.status not in PRE_DELIVERY_STATUSES:
                messages.error(request, "Không thể duyệt hủy đơn đã bắt đầu giao.")
                return redirect(f"{reverse('staff_orders:dashboard')}?workspace=orders&view=cancellations")
            cancellation.status = OrderCancellationRequest.Status.APPROVED
            cancellation.resolved_by = request.user
            cancellation.resolved_at = timezone.now()
            cancellation.manager_resolution_reason = "Quản lý đã duyệt yêu cầu hủy."
            email_subject = f"Yêu cầu hủy đơn {order.order_number} đã được duyệt"
            email_body = (
                f"Yêu cầu hủy đơn {order.order_number} đã được Quản lý duyệt.\n"
                f"Lý do: {cancellation.reason}\n"
                + (
                    "Cửa hàng đã ghi nhận yêu cầu hoàn tiền."
                    if order.refund_status == Order.RefundStatus.REQUESTED
                    else "Bạn không cần thanh toán đơn hàng này."
                )
            )
        else:
            rejection_reason = form.cleaned_data["reason"]
            cancellation.status = OrderCancellationRequest.Status.REJECTED
            cancellation.resolved_by = request.user
            cancellation.resolved_at = timezone.now()
            cancellation.manager_resolution_reason = rejection_reason
            email_subject = f"Yêu cầu hủy đơn {order.order_number} chưa được chấp nhận"
            email_body = (
                f"Yêu cầu hủy đơn {order.order_number} chưa được chấp nhận.\n"
                f"Lý do: {rejection_reason}\n"
                "Đơn hàng vẫn tiếp tục theo trạng thái hiện tại."
            )
        cancellation.save(
            update_fields=[
                "status",
                "resolved_by",
                "resolved_at",
                "manager_resolution_reason",
                "updated_at",
            ]
        )
        if form.cleaned_data["decision"] == "approve":
            _cancel_order(order, request.user, cancellation.reason)

    sent = _send_cancellation_email(
        order,
        email_subject,
        email_body,
        recipient_email=email_recipient,
    )
    _cancellation_email_message(request, sent)
    decision_label = "duyệt hủy" if form.cleaned_data["decision"] == "approve" else "từ chối"
    messages.success(request, f"Đã {decision_label} yêu cầu cho đơn {order.order_number}.")
    return redirect(f"{reverse('staff_orders:dashboard')}?workspace=orders&view=cancellations")


@login_required
@require_POST
def manager_resolve_delivery_issue(request, issue_id):
    if not _can_manage_catalog(request.user):
        raise PermissionDenied
    issue_preview = get_object_or_404(
        DeliveryIssue.objects.select_related("reported_by"),
        pk=issue_id,
        status=DeliveryIssue.Status.PENDING,
    )
    is_delivery_failure = (
        issue_preview.source == DeliveryIssue.Source.STAFF_DELIVERY
    )
    queue_view = "delivery_failures" if is_delivery_failure else "delivery_issues"
    form_class = (
        DeliveryFailureResolutionForm
        if is_delivery_failure
        else DeliveryIssueResolutionForm
    )
    form = form_class(request.POST)
    if not form.is_valid():
        errors = "; ".join(
            error for error_list in form.errors.values() for error in error_list
        )
        messages.error(request, errors or "Thông tin xử lý đơn hàng không hợp lệ.")
        return redirect(
            f"{reverse('staff_orders:dashboard')}?workspace=orders&view={queue_view}&issue={issue_id}"
        )

    email_recipient = ""
    cancelled = False
    with transaction.atomic():
        issue = get_object_or_404(
            DeliveryIssue.objects.select_for_update().select_related("reported_by"),
            pk=issue_id,
            status=DeliveryIssue.Status.PENDING,
        )
        issue_is_delivery_failure = (
            issue.source == DeliveryIssue.Source.STAFF_DELIVERY
        )
        if issue_is_delivery_failure != is_delivery_failure:
            messages.error(request, "Đơn hàng đã thay đổi trạng thái xử lý. Vui lòng tải lại.")
            return redirect(
                f"{reverse('staff_orders:dashboard')}?workspace=orders&view={queue_view}"
            )
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=issue.order_id,
            status=Order.Status.DELIVERY_ISSUE,
        )
        decision = form.cleaned_data["decision"]
        resolution = form.cleaned_data["resolution"]
        if decision == DeliveryIssue.Resolution.CANCELLED:
            email_recipient = order.customer_email
            cancellation = (
                OrderCancellationRequest.objects.select_for_update()
                .filter(
                    order=order,
                    status__in=OPEN_CANCELLATION_STATUSES,
                )
                .first()
            )
            now = timezone.now()
            reason = f"Giao hàng thất bại: {resolution}"
            if cancellation:
                cancellation.status = OrderCancellationRequest.Status.APPROVED
                cancellation.manager_resolution_reason = resolution
                cancellation.resolved_by = request.user
                cancellation.resolved_at = now
                cancellation.save(
                    update_fields=[
                        "status",
                        "manager_resolution_reason",
                        "resolved_by",
                        "resolved_at",
                        "updated_at",
                    ]
                )
            else:
                OrderCancellationRequest.objects.create(
                    order=order,
                    source=OrderCancellationRequest.Source.STAFF,
                    status=OrderCancellationRequest.Status.APPROVED,
                    reason=reason,
                    requested_by=request.user,
                    contact_outcome=OrderCancellationRequest.ContactOutcome.NOT_REQUIRED,
                    manager_resolution_reason=resolution,
                    resolved_by=request.user,
                    resolved_at=now,
                )
            issue.status = DeliveryIssue.Status.RESOLVED
            issue.resolution_outcome = decision
            issue.resolution = resolution
            issue.resolved_by = request.user
            issue.resolved_at = now
            issue.save(
                update_fields=[
                    "status",
                    "resolution_outcome",
                    "resolution",
                    "resolved_by",
                    "resolved_at",
                ]
            )
            _cancel_order(order, request.user, reason)
            cancelled = True
        else:
            issue.status = DeliveryIssue.Status.RESOLVED
            issue.resolution_outcome = decision
            issue.resolution = resolution
            issue.resolved_by = request.user
            issue.resolved_at = timezone.now()
            issue.save(
                update_fields=[
                    "status",
                    "resolution_outcome",
                    "resolution",
                    "resolved_by",
                    "resolved_at",
                ]
            )

            if decision == DeliveryIssue.Resolution.CONFIRMED:
                order.status = Order.Status.DELIVERED
                order.delivery_confirmation_method = Order.DeliveryConfirmationMethod.MANAGER
                order.delivery_confirmed_at = timezone.now()
            else:
                order.status = Order.Status.DELIVERING
                order.delivery_confirmation_method = ""
                order.delivery_confirmed_at = None
            order.delivery_confirmation_deadline = None
            order.save(
                update_fields=[
                    "status",
                    "delivery_confirmation_deadline",
                    "delivery_confirmed_at",
                    "delivery_confirmation_method",
                    "updated_at",
                ]
            )

    if cancelled:
        sent = _send_cancellation_email(
            order,
            f"Đơn hàng {order.order_number} đã được hủy",
            (
                f"Đơn hàng {order.order_number} đã được hủy do giao hàng thất bại.\n"
                f"Ghi chú xử lý: {resolution}\n"
                "Nếu đơn đã thanh toán trực tuyến, khoản hoàn tiền cần được xử lý thủ công."
            ),
            recipient_email=email_recipient,
        )
        _cancellation_email_message(request, sent)
        if order.refund_status == Order.RefundStatus.REQUESTED:
            messages.warning(
                request,
                f"Đã hủy đơn {order.order_number}; khoản đã thanh toán đang chờ hoàn tiền thủ công.",
            )
        else:
            messages.success(request, f"Đã hủy đơn {order.order_number}.")
    else:
        messages.success(
            request,
            f"Đã cập nhật xử lý giao hàng đơn {order.order_number}.",
        )
    return redirect(
        f"{reverse('staff_orders:dashboard')}?workspace=orders&view={queue_view}"
    )


@login_required
@require_POST
def manager_resolve_order_care_request(request, care_request_id):
    if not _can_manage_catalog(request.user):
        raise PermissionDenied
    form = OrderCareRequestResolutionForm(request.POST)
    if not form.is_valid():
        errors = "; ".join(
            error for error_list in form.errors.values() for error in error_list
        )
        messages.error(request, errors or "Thông tin xử lý yêu cầu không hợp lệ.")
        return redirect(
            f"{reverse('staff_orders:dashboard')}?workspace=orders&view=customer_care"
        )

    with transaction.atomic():
        care_request = get_object_or_404(
            OrderCareRequest.objects.select_for_update().select_related("order"),
            pk=care_request_id,
            status=OrderCareRequest.Status.PENDING,
        )
        care_request.status = (
            OrderCareRequest.Status.APPROVED
            if form.cleaned_data["decision"] == "approve"
            else OrderCareRequest.Status.REJECTED
        )
        care_request.resolution_note = form.cleaned_data["resolution_note"]
        care_request.resolved_by = request.user
        care_request.resolved_at = timezone.now()
        care_request.save(
            update_fields=[
                "status",
                "resolution_note",
                "resolved_by",
                "resolved_at",
            ]
        )

    if (
        care_request.request_type == OrderCareRequest.RequestType.RETURN
        and care_request.status == OrderCareRequest.Status.APPROVED
        and care_request.order.payment_method != Order.PaymentMethod.COD
    ):
        messages.warning(
            request,
            "Đã chấp thuận yêu cầu đổi/trả. Việc hoàn tiền (nếu có) vẫn cần xử lý thủ công; hệ thống chưa tự hoàn tiền.",
        )
    else:
        messages.success(
            request,
            f"Đã {care_request.get_status_display().lower()} yêu cầu {care_request.get_request_type_display().lower()} của đơn {care_request.order.order_number}.",
        )
    return redirect(
        f"{reverse('staff_orders:dashboard')}?workspace=orders&view=customer_care"
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def access_order_pii(request, order_id):
    if not _can_manage_catalog(request.user):
        raise PermissionDenied

    purge_expired_order_pii()
    order = get_object_or_404(Order, pk=order_id)
    if order.customer_care_period_open:
        messages.error(
            request,
            "Trong 7 ngày kể từ khi giao, thông tin chỉ được xem trong quá trình xử lý khiếu nại của Quản lý.",
        )
        return redirect(
            f"{reverse('staff_orders:dashboard')}?workspace=orders&view=customer_care"
        )
    if not order.can_request_pii_access():
        messages.error(
            request,
            "Thông tin cá nhân không còn khả dụng hoặc đã được xóa theo thời hạn lưu trữ.",
        )
        if request.user.is_superuser:
            return redirect(reverse("admin:orders_order_change", args=[order.pk]))
        return redirect(
            f"{reverse('staff_orders:dashboard')}?workspace=orders&view=orders"
        )

    form = OrderPiiAccessForm(request.POST or None)
    if request.method == "GET":
        response = render(
            request,
            "orders/order_pii_access.html",
            {"order": order, "form": form},
        )
        response["Cache-Control"] = "private, no-store"
        return response
    if not form.is_valid():
        response = render(
            request,
            "orders/order_pii_access.html",
            {"order": order, "form": form},
            status=400,
        )
        response["Cache-Control"] = "private, no-store"
        return response

    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
        if not order.can_request_pii_access():
            messages.error(
                request,
                "Thông tin cá nhân không còn khả dụng hoặc đã được xóa theo thời hạn lưu trữ.",
            )
            if request.user.is_superuser:
                return redirect(reverse("admin:orders_order_change", args=[order.pk]))
            return redirect(
                f"{reverse('staff_orders:dashboard')}?workspace=orders&view=orders"
            )
        pii_snapshot = decrypt_order_pii_snapshot(order.customer_pii_encrypted)
        access_log = OrderPiiAccessLog.objects.create(
            order=order,
            accessed_by=request.user,
            reason=form.cleaned_data["reason"],
        )

    response = render(
        request,
        "orders/order_pii_access.html",
        {
            "order": order,
            "access_log": access_log,
            "customer_data": pii_snapshot.get("order", {}),
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def manager_cancel_order(request, order_id):
    if not _can_manage_catalog(request.user):
        raise PermissionDenied
    form = CancellationReasonForm(request.POST)
    if not form.is_valid():
        errors = "; ".join(form.errors.get("reason", [])) or "Vui lòng nhập lý do hủy."
        messages.error(request, errors)
        if request.user.is_superuser:
            return redirect(
                f"{reverse('staff_orders:dashboard')}?section=orders&order={order_id}#orders"
            )
        return redirect(f"{reverse('staff_orders:dashboard')}?workspace=orders")

    email_recipient = ""
    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
        email_recipient = order.customer_email
        if order.status not in PRE_DELIVERY_STATUSES:
            messages.error(request, "Chỉ có thể hủy trực tiếp đơn chưa bắt đầu giao.")
            if request.user.is_superuser:
                return redirect(
                    f"{reverse('staff_orders:dashboard')}?section=orders&order={order.pk}#orders"
                )
            return redirect(f"{reverse('staff_orders:dashboard')}?workspace=orders")
        if OrderCancellationRequest.objects.filter(
            order=order,
            status__in=OPEN_CANCELLATION_STATUSES,
        ).exists():
            messages.error(request, "Hãy xử lý yêu cầu hủy đang mở trong mục Yêu cầu hủy.")
            if request.user.is_superuser:
                return redirect(
                    f"{reverse('staff_orders:dashboard')}?section=orders&order={order.pk}#orders"
                )
            return redirect(
                f"{reverse('staff_orders:dashboard')}?workspace=orders&view=cancellations"
            )

        now = timezone.now()
        reason = form.cleaned_data["reason"]
        OrderCancellationRequest.objects.create(
            order=order,
            source=OrderCancellationRequest.Source.STAFF,
            status=OrderCancellationRequest.Status.APPROVED,
            reason=reason,
            requested_by=request.user,
            contact_outcome=OrderCancellationRequest.ContactOutcome.NOT_REQUIRED,
            manager_resolution_reason=reason,
            resolved_by=request.user,
            resolved_at=now,
        )
        _cancel_order(order, request.user, reason)

    sent = _send_cancellation_email(
        order,
        f"Đơn hàng {order.order_number} đã được hủy",
        f"Đơn hàng {order.order_number} đã được hủy bởi cửa hàng.\nLý do: {reason}",
        recipient_email=email_recipient,
    )
    _cancellation_email_message(request, sent)
    messages.success(request, f"Đã hủy đơn {order.order_number} với lý do đã lưu.")
    if request.user.is_superuser:
        return redirect(f"{reverse('staff_orders:dashboard')}?section=orders&order={order.pk}#orders")
    return redirect(f"{reverse('staff_orders:dashboard')}?workspace=orders#staff-workspace")


@login_required
@require_http_methods(["GET", "POST"])
def staff_create_product(request):
    if not _can_manage_catalog(request.user):
        raise PermissionDenied

    if request.method == "GET":
        return render(
            request,
            "orders/product_create.html",
            {
                "product_form": ProductCreateForm(),
                "employee_role": request.user.get_staff_role_display(),
                "catalog_url": (
                    f"{reverse('staff_orders:dashboard')}?section=products#products"
                    if request.user.is_superuser
                    else f"{reverse('staff_orders:dashboard')}?workspace=menu"
                ),
            },
        )

    post_data = request.POST.copy()
    save_mode = post_data.get("save_mode")
    if save_mode == "publish":
        post_data["is_available"] = "on"
    elif save_mode == "draft":
        post_data.pop("is_available", None)
    form = ProductCreateForm(post_data, request.FILES)
    if form.is_valid():
        if save_mode == "publish":
            publish_requirements = {
                "ingredients": bool(form.cleaned_data["ingredients"].strip()),
                "calories": bool(form.cleaned_data["calories"]),
                "protein": form.cleaned_data["protein"] > 0,
                "serving": bool(form.cleaned_data["serving"].strip()),
                "image": bool(form.cleaned_data["image"]),
            }
            if form.cleaned_data["category"] == Product.Category.DRY_GOODS:
                publish_requirements["stock_quantity"] = (
                    form.cleaned_data["stock_quantity"] is not None
                )
            missing_requirements = [
                field_name
                for field_name, is_complete in publish_requirements.items()
                if not is_complete
            ]
            for field_name in missing_requirements:
                form.add_error(field_name, "Cần điền thông tin này để mở bán món.")

    if form.is_valid():
        with transaction.atomic():
            product = form.save()
            _record_product_activity(
                product=product,
                actor=request.user,
                action=ProductActivity.Action.CREATED,
                new_value=format(product.price, ".2f"),
            )
            if product.tracks_inventory and product.stock_quantity is not None:
                _record_product_activity(
                    product=product,
                    actor=request.user,
                    action=ProductActivity.Action.INVENTORY_CHANGED,
                    new_value=(
                        f"{product.stock_quantity} · ngưỡng {product.low_stock_threshold}"
                    ),
                )
        messages.success(request, f"Đã thêm sản phẩm {product.name}.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return render(
            request,
            "orders/product_create.html",
            {
                "product_form": form,
                "employee_role": request.user.get_staff_role_display(),
                "catalog_url": (
                    f"{reverse('staff_orders:dashboard')}?section=products#products"
                    if request.user.is_superuser
                    else f"{reverse('staff_orders:dashboard')}?workspace=menu"
                ),
            },
            status=400,
        )
    if not request.user.is_superuser:
        if form.is_valid():
            return redirect(
                f"{reverse('staff_orders:dashboard')}?workspace=menu&product={product.pk}#manager-products"
            )
        return redirect(f"{reverse('staff_orders:dashboard')}?workspace=menu#manager-products")
    return redirect(f"{reverse('staff_orders:dashboard')}?section=products#products")


@login_required
@require_POST
def staff_toggle_product_availability(request, product_id):
    if not _can_access_employee_workspace(request.user):
        raise PermissionDenied

    menu_query = urlencode(
        {
            "workspace": "menu",
            "filter": request.GET.get("filter", "all"),
            "q": request.GET.get("q", "")[:100],
        }
    )
    requested_value = request.POST.get("is_available")
    if requested_value not in {"true", "false"}:
        messages.error(request, "Trạng thái món không hợp lệ.")
        return redirect(
            f"{reverse('staff_orders:dashboard')}?{menu_query}#staff-workspace"
        )

    is_available = requested_value == "true"
    with transaction.atomic():
        product = get_object_or_404(Product.objects.select_for_update(), pk=product_id)
        old_is_available = product.is_available
        if old_is_available == is_available:
            messages.info(
                request,
                f"Món {product.name} đã ở trạng thái "
                f"{'đang bán' if is_available else 'tạm hết hàng'}.",
            )
        else:
            product.is_available = is_available
            product.save(update_fields=["is_available", "updated_at"])
            _record_product_activity(
                product=product,
                actor=request.user,
                action=ProductActivity.Action.AVAILABILITY_CHANGED,
                old_value="Đang bán" if old_is_available else "Tạm ngưng",
                new_value="Đang bán" if is_available else "Tạm ngưng",
            )
            messages.success(
                request,
                f"Đã {'mở bán lại' if is_available else 'tạm ngưng bán'} món {product.name}.",
            )
    return redirect(
        f"{reverse('staff_orders:dashboard')}?{menu_query}#staff-workspace"
    )


@login_required
@require_POST
def staff_request_inventory_restock(request, product_id):
    if not _can_access_employee_workspace(request.user):
        raise PermissionDenied

    with transaction.atomic():
        product = get_object_or_404(
            Product.objects.select_for_update(),
            pk=product_id,
            category=Product.Category.DRY_GOODS,
        )
        restock_request = InventoryRestockRequest.objects.select_for_update().filter(
            product=product,
            status=InventoryRestockRequest.Status.STAFF_ALERT,
        ).first()
        if not restock_request:
            messages.info(
                request,
                f"Cảnh báo bổ sung {product.name} đã được gửi hoặc không còn mở.",
            )
        else:
            restock_request.status = InventoryRestockRequest.Status.MANAGER_REVIEW
            restock_request.requested_by = request.user
            restock_request.save(
                update_fields=["status", "requested_by", "updated_at"]
            )

    if restock_request:
        messages.success(
            request,
            f"Đã gửi yêu cầu bổ sung {product.name} cho Quản lý.",
        )
    return redirect(f"{reverse('staff_orders:dashboard')}?workspace=menu#staff-workspace")


@login_required
@require_POST
def manager_fulfill_inventory_restock(request, restock_request_id):
    if not _can_manage_catalog(request.user):
        raise PermissionDenied

    with transaction.atomic():
        restock_request = InventoryRestockRequest.objects.filter(
            pk=restock_request_id,
            status=InventoryRestockRequest.Status.MANAGER_REVIEW,
        ).first()
        if not restock_request:
            messages.error(request, "Yêu cầu bổ sung này đã được xử lý hoặc không còn mở.")
        elif not restock_request.product_id:
            restock_request = InventoryRestockRequest.objects.select_for_update().get(
                pk=restock_request_id,
                status=InventoryRestockRequest.Status.MANAGER_REVIEW,
            )
            restock_request.status = InventoryRestockRequest.Status.CANCELLED
            restock_request.requested_quantity = 0
            restock_request.save(
                update_fields=["status", "requested_quantity", "updated_at"]
            )
            messages.error(request, "Sản phẩm của yêu cầu này không còn tồn tại.")
        else:
            product, outstanding_quantity, fulfilled = fulfill_inventory_backorders(
                restock_request.product_id,
                actor=request.user,
            )
            restock_request = InventoryRestockRequest.objects.select_for_update().filter(
                pk=restock_request_id,
                status=InventoryRestockRequest.Status.MANAGER_REVIEW,
            ).first()
            if not restock_request:
                messages.info(request, "Yêu cầu này đã được quản lý khác xử lý.")
            elif outstanding_quantity == 0:
                restock_request.status = InventoryRestockRequest.Status.CANCELLED
                restock_request.requested_quantity = 0
                restock_request.available_quantity = product.stock_quantity or 0
                restock_request.save(
                    update_fields=[
                        "status",
                        "requested_quantity",
                        "available_quantity",
                        "updated_at",
                    ]
                )
                messages.info(
                    request,
                    f"Không còn đơn chờ nhập hàng cho {product.name}.",
                )
            elif not product.tracks_inventory:
                restock_request.status = InventoryRestockRequest.Status.CANCELLED
                restock_request.requested_quantity = 0
                restock_request.save(
                    update_fields=["status", "requested_quantity", "updated_at"]
                )
                messages.error(
                    request,
                    f"{product.name} không còn được quản lý tồn kho.",
                )
            elif not fulfilled:
                restock_request.requested_quantity = outstanding_quantity
                restock_request.available_quantity = product.stock_quantity or 0
                restock_request.save(
                    update_fields=[
                        "requested_quantity",
                        "available_quantity",
                        "updated_at",
                    ]
                )
                messages.error(
                    request,
                    f"Cần cập nhật tồn kho {product.name} đủ ít nhất "
                    f"{outstanding_quantity} trước khi xác nhận.",
                )
            else:
                restock_request.status = InventoryRestockRequest.Status.FULFILLED
                restock_request.fulfilled_by = request.user
                restock_request.fulfilled_at = timezone.now()
                restock_request.save(
                    update_fields=[
                        "status",
                        "fulfilled_by",
                        "fulfilled_at",
                        "updated_at",
                    ]
                )
                messages.success(
                    request,
                    f"Đã xác nhận bổ sung {product.name}.",
                )

    return redirect(
        f"{reverse('staff_orders:dashboard')}?workspace=inventory#manager-inventory"
    )


@login_required
@require_POST
def staff_update_product(request, product_id):
    if not _can_manage_catalog(request.user):
        raise PermissionDenied

    with transaction.atomic():
        workspace = request.GET.get("workspace", "menu")
        if workspace not in {"menu", "inventory"}:
            workspace = "menu"
        product_queryset = Product.objects.select_for_update()
        if workspace == "inventory" and not request.user.is_superuser:
            product_queryset = product_queryset.filter(
                category=Product.Category.DRY_GOODS
            )
        product = get_object_or_404(product_queryset, pk=product_id)
        old_values = {
            "price": product.price,
            "stock_quantity": product.stock_quantity,
            "low_stock_threshold": product.low_stock_threshold,
            "is_available": product.is_available,
        }
        if request.user.is_superuser:
            form_class = ProductQuickEditForm
        elif workspace == "inventory":
            form_class = ProductInventoryUpdateForm
        else:
            form_class = ProductManagerUpdateForm
        form = form_class(request.POST, instance=product)
        if form.is_valid():
            product = form.save()
            if product.price != old_values["price"]:
                _record_product_activity(
                    product=product,
                    actor=request.user,
                    action=ProductActivity.Action.PRICE_CHANGED,
                    old_value=format(old_values["price"], ".2f"),
                    new_value=format(product.price, ".2f"),
                )
            if (
                product.stock_quantity != old_values["stock_quantity"]
                or product.low_stock_threshold != old_values["low_stock_threshold"]
            ):
                old_stock = (
                    "Chưa cập nhật"
                    if old_values["stock_quantity"] is None
                    else str(old_values["stock_quantity"])
                )
                new_stock = (
                    "Chưa cập nhật"
                    if product.stock_quantity is None
                    else str(product.stock_quantity)
                )
                _record_product_activity(
                    product=product,
                    actor=request.user,
                    action=ProductActivity.Action.INVENTORY_CHANGED,
                    old_value=(
                        f"{old_stock} · ngưỡng {old_values['low_stock_threshold']}"
                    ),
                    new_value=(
                        f"{new_stock} · ngưỡng {product.low_stock_threshold}"
                    ),
                )
            if product.is_available != old_values["is_available"]:
                _record_product_activity(
                    product=product,
                    actor=request.user,
                    action=ProductActivity.Action.AVAILABILITY_CHANGED,
                    old_value="Đang bán" if old_values["is_available"] else "Tạm ngưng",
                    new_value="Đang bán" if product.is_available else "Tạm ngưng",
                )
            messages.success(request, f"Đã cập nhật sản phẩm {product.name}.")
        else:
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
    if not request.user.is_superuser:
        anchor = "manager-products" if workspace == "menu" else "manager-inventory"
        return redirect(
            f"{reverse('staff_orders:dashboard')}?workspace={workspace}&product={product.pk}#{anchor}"
        )
    page = request.GET.get("page", "1")
    if not page.isdecimal():
        page = "1"
    return redirect(f"{reverse('staff_orders:dashboard')}?section=products&page={page}#products")
