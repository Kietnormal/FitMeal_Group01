from django.core.management.base import BaseCommand

from apps.payments.gateway import expire_pending_payments


class Command(BaseCommand):
    help = "Cancel orders whose bank transfer payments have expired."

    def handle(self, *args, **options):
        expired = expire_pending_payments()
        self.stdout.write(self.style.SUCCESS(f"Expired {expired} pending payments."))
