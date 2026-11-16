from django.core.management.base import BaseCommand

from apps.core.operations import create_database_backup


class Command(BaseCommand):
    help = "Create an encrypted JSON backup of the FitMeal database."

    def handle(self, *args, **options):
        backup = create_database_backup()
        self.stdout.write(self.style.SUCCESS(f"Encrypted backup created: {backup}"))
