from apps.orders.privacy import build_order_pii_snapshot, encrypt_order_pii_snapshot
from django.db import migrations


def encrypt_cancelled_orders(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    CancellationRequest = apps.get_model("orders", "OrderCancellationRequest")
    DeliveryIssue = apps.get_model("orders", "DeliveryIssue")
    database = schema_editor.connection.alias

    orders = Order.objects.using(database).filter(
        status="cancelled",
        customer_pii_encrypted="",
    )
    for order in orders.iterator():
        cancellations = list(
            CancellationRequest.objects.using(database)
            .filter(order_id=order.pk)
            .order_by("pk")
        )
        delivery_issues = list(
            DeliveryIssue.objects.using(database)
            .filter(order_id=order.pk)
            .order_by("pk")
        )
        order.customer_pii_encrypted = encrypt_order_pii_snapshot(
            build_order_pii_snapshot(order, cancellations, delivery_issues)
        )
        for field in (
            "customer_name",
            "customer_email",
            "customer_phone",
            "address",
            "district",
            "city",
            "note",
            "cancellation_reason",
        ):
            setattr(order, field, "")
        order.save(
            using=database,
            update_fields=[
                "customer_pii_encrypted",
                "customer_name",
                "customer_email",
                "customer_phone",
                "address",
                "district",
                "city",
                "note",
                "cancellation_reason",
            ],
        )

        for cancellation in cancellations:
            cancellation.reason = ""
            cancellation.contact_notes = ""
            cancellation.manager_resolution_reason = ""
            fields = ["reason", "contact_notes", "manager_resolution_reason"]
            if cancellation.source == "customer":
                cancellation.requested_by = None
                fields.append("requested_by")
            cancellation.save(using=database, update_fields=fields)

        for issue in delivery_issues:
            issue.details = ""
            issue.resolution = ""
            issue.reported_by = None
            issue.save(
                using=database,
                update_fields=["details", "resolution", "reported_by"],
            )


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0006_deliveryissue_order_delivery_confirmation_deadline_and_more"),
    ]

    operations = [
        migrations.RunPython(encrypt_cancelled_orders, migrations.RunPython.noop),
    ]
