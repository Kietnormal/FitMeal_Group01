import base64
import hashlib
import json

from cryptography.fernet import Fernet
from django.conf import settings


ORDER_PII_KEY_CONTEXT = "fitmeal:delivered-order-pii:v1:"
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
    key_material = hashlib.sha256(
        f"{ORDER_PII_KEY_CONTEXT}{settings.SECRET_KEY}".encode("utf-8")
    ).digest()
    key = base64.urlsafe_b64encode(key_material)
    serialized = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return Fernet(key).encrypt(serialized).decode("ascii")
