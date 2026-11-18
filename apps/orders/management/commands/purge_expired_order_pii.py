from django.core.management.base import BaseCommand

from apps.orders.privacy import purge_expired_order_pii


class Command(BaseCommand):
    help = "Permanently remove personal data from orders after its retention period."

    def handle(self, *args, **options):
        purged = purge_expired_order_pii()
        self.stdout.write(f"Purged personal data from {purged} expired order(s).")
