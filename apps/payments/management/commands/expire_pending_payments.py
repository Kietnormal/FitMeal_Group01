from django.core.management.base import BaseCommand

from apps.payments.gateway import expire_pending_payments


class Command(BaseCommand):
    help = "Cancel VNPay orders that were not paid before their 15-minute deadline."

    def handle(self, *args, **options):
        expired = expire_pending_payments()
        self.stdout.write(self.style.SUCCESS(f"Expired {expired} pending payments."))
