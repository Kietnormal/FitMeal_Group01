from django.core.management.base import BaseCommand

from apps.orders.delivery import finalize_expired_delivery_confirmations


class Command(BaseCommand):
    help = "Automatically complete delivery confirmations whose three-minute deadline passed."

    def handle(self, *args, **options):
        total = 0
        while True:
            finalized = finalize_expired_delivery_confirmations()
            if not finalized:
                break
            total += finalized
        self.stdout.write(f"Completed {total} expired delivery confirmation(s).")
