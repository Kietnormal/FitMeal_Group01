from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Order


DELIVERY_CONFIRMATION_MINUTES = 3


def begin_customer_delivery_confirmation(order, *, now=None):
    now = now or timezone.now()
    order.status = Order.Status.AWAITING_CUSTOMER_CONFIRMATION
    order.delivery_confirmation_deadline = now + timedelta(
        minutes=DELIVERY_CONFIRMATION_MINUTES
    )
    order.save(update_fields=["status", "delivery_confirmation_deadline", "updated_at"])


def finalize_expired_delivery_confirmations(*, now=None, batch_size=100):
    now = now or timezone.now()
    order_ids = list(
        Order.objects.filter(
            status=Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
            delivery_confirmation_deadline__lte=now,
        )
        .order_by("delivery_confirmation_deadline", "pk")
        .values_list("pk", flat=True)[:batch_size]
    )
    finalized = 0
    for order_id in order_ids:
        with transaction.atomic():
            order = (
                Order.objects.select_for_update()
                .filter(
                    pk=order_id,
                    status=Order.Status.AWAITING_CUSTOMER_CONFIRMATION,
                    delivery_confirmation_deadline__lte=now,
                )
                .first()
            )
            if order is None:
                continue
            order.status = Order.Status.DELIVERED
            order.delivery_confirmation_deadline = None
            order.delivery_confirmed_at = now
            order.delivery_confirmation_method = Order.DeliveryConfirmationMethod.AUTOMATIC
            order.save(
                update_fields=[
                    "status",
                    "delivery_confirmation_deadline",
                    "delivery_confirmed_at",
                    "delivery_confirmation_method",
                    "updated_at",
                ]
            )
            finalized += 1
    return finalized
