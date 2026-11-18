import base64
import hashlib
import json
import uuid
from datetime import timedelta

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone


ORDER_PII_KEY_CONTEXT = "fitmeal:delivered-order-pii:v1:"
CUSTOMER_CARE_PERIOD = timedelta(days=7)
ORDER_PII_RETENTION_PERIOD = timedelta(days=365)
ORDER_PII_FIELDS = (
    "customer_name",
    "customer_email",
    "customer_phone",
    "address",
    "district",
    "city",
    "note",
    "cancellation_reason",
)
ORDER_REDACTED_FIELDS = (
    "customer_name",
    "customer_email",
    "customer_phone",
    "address",
    "note",
    "cancellation_reason",
)


def build_order_pii_snapshot(order, cancellation_requests, delivery_issues=()):
    return {
        "order": {field: getattr(order, field) for field in ORDER_PII_FIELDS},
        "cancellation_requests": [
            {
                "id": request.pk,
                "source": request.source,
                "reason": request.reason,
                "contact_notes": request.contact_notes,
                "manager_resolution_reason": request.manager_resolution_reason,
            }
            for request in cancellation_requests
        ],
        "delivery_issues": [
            {
                "id": issue.pk,
                "details": issue.details,
                "resolution": issue.resolution,
                "reported_by_id": issue.reported_by_id,
            }
            for issue in delivery_issues
        ],
    }


def encrypt_order_pii_snapshot(snapshot):
    key = _order_pii_key()
    serialized = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return Fernet(key).encrypt(serialized).decode("ascii")


def decrypt_order_pii_snapshot(encrypted_snapshot):
    return json.loads(Fernet(_order_pii_key()).decrypt(encrypted_snapshot.encode("ascii")))


def _order_pii_key():
    key_material = hashlib.sha256(
        f"{ORDER_PII_KEY_CONTEXT}{settings.SECRET_KEY}".encode("utf-8")
    ).digest()
    return base64.urlsafe_b64encode(key_material)


def purge_expired_order_pii(now=None):
    from .models import DeliveryIssue, Order, OrderCancellationRequest, OrderCareRequest

    now = now or timezone.now()
    cutoff = now - ORDER_PII_RETENTION_PERIOD
    delivered_before_cutoff = Q(status=Order.Status.DELIVERED) & (
        Q(delivery_confirmed_at__lte=cutoff)
        | Q(delivery_confirmed_at__isnull=True, updated_at__lte=cutoff)
    )
    cancelled_before_cutoff = Q(status=Order.Status.CANCELLED) & (
        Q(cancelled_at__lte=cutoff)
        | Q(cancelled_at__isnull=True, updated_at__lte=cutoff)
    )
    expired_orders = Order.objects.filter(
        customer_pii_purged_at__isnull=True,
    ).filter(delivered_before_cutoff | cancelled_before_cutoff)

    with transaction.atomic():
        order_ids = list(expired_orders.values_list("pk", flat=True))
        if not order_ids:
            return 0

        Order.objects.filter(pk__in=order_ids).update(
            customer_name="",
            customer_email="",
            customer_phone="",
            address="",
            customer=None,
            note="",
            cancellation_reason="",
            customer_pii_encrypted="",
            customer_pii_purged_at=now,
        )
        for order_id in order_ids:
            Order.objects.filter(pk=order_id).update(tracking_token=uuid.uuid4())
        OrderCancellationRequest.objects.filter(order_id__in=order_ids).update(
            reason="",
            contact_notes="",
            manager_resolution_reason="",
            requested_by=None,
        )
        DeliveryIssue.objects.filter(order_id__in=order_ids).update(
            details="",
            resolution="",
            reported_by=None,
        )
        OrderCareRequest.objects.filter(order_id__in=order_ids).update(
            details="",
            resolution_note="",
            requested_by=None,
        )

    return len(order_ids)
