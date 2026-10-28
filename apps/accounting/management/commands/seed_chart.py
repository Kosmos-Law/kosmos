from django.core.management.base import BaseCommand

from apps.accounting.chart import seed_default_chart


class Command(BaseCommand):
    help = (
        "Add the default chart of accounts for a law firm. Accounts whose "
        "code already exists are left alone, so the command is safe to repeat."
    )

    def handle(self, *args, **options):
        added = seed_default_chart()
        self.stdout.write(f"{added} accounts added.")
