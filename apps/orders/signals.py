from decimal import Decimal

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import PointsTransaction

from .models import Order

POINTS_PER_10K = Decimal("10000")


@receiver(post_save, sender=Order)
def synchronize_order_points(sender, instance, **kwargs):
    if not instance.customer_id:
        return

    with transaction.atomic():
        expected_points = int(instance.subtotal // POINTS_PER_10K)
        earned = PointsTransaction.objects.filter(
            order=instance,
            kind=PointsTransaction.Kind.EARNED,
        ).first()

        if instance.status == Order.Status.DELIVERED:
            if expected_points:
                earned, created = PointsTransaction.objects.get_or_create(
                    order=instance,
                    kind=PointsTransaction.Kind.EARNED,
                    defaults={
                        "user_id": instance.customer_id,
                        "points": expected_points,
                        "description": f"Tích điểm đơn {instance.order_number}",
                    },
                )
                if not created and earned.points != expected_points:
                    earned.points = expected_points
                    earned.save(update_fields=["points"])
            reversal = PointsTransaction.objects.filter(
                order=instance,
                kind=PointsTransaction.Kind.REVERSAL,
            ).first()
            if reversal and reversal.points:
                reversal.points = 0
                reversal.description = f"Khôi phục điểm đơn {instance.order_number}"
                reversal.save(update_fields=["points", "description"])
        elif instance.status == Order.Status.CANCELLED and earned and earned.points > 0:
            PointsTransaction.objects.get_or_create(
                order=instance,
                kind=PointsTransaction.Kind.REVERSAL,
                defaults={
                    "user_id": instance.customer_id,
                    "points": -earned.points,
                    "description": f"Hoàn điểm do hủy đơn {instance.order_number}",
                },
            )
