"""Send the event notifications that have come due.

The background worker runs this every minute (the event-reminders
schedule in apps/management/schedules.py); the command runs it by hand.
"""

from django.core.management.base import BaseCommand

from apps.calendar import reminders


class Command(BaseCommand):
    help = "Sends the event notifications that have come due, by email or ntfy."

    def handle(self, *args, **options):
        sent, errors = reminders.send_due()
        self.stdout.write(
            self.style.SUCCESS(f"Sent {sent} notification(s), {errors} error(s)")
        )
