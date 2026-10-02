from django.conf import settings
from django.core.management.base import BaseCommand

from apps.case.ai.purge import DEFAULT_RETENTION_DAYS, purge_closed_chats


class Command(BaseCommand):
    help = (
        "Delete AI chat history (conversations, messages and their history "
        "rows) for matters closed longer than the retention window. Chats "
        "are working notes with no lasting value once a matter closes; the "
        "client file lives in Drive and Gmail. Scheduled weekly by "
        "setup_schedules."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=(
                "Retention window after closing, in days (default: "
                f"CHAT_RETENTION_DAYS, or {DEFAULT_RETENTION_DAYS} when that is 0)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days is None:
            # CHAT_RETENTION_DAYS=0 switches the scheduled purge off; a purge
            # run by hand still needs a window, so fall back to the default.
            days = settings.CHAT_RETENTION_DAYS or DEFAULT_RETENTION_DAYS
        stats = purge_closed_chats(days=days, dry_run=options["dry_run"])
        prefix = "[dry-run] " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Purged {stats['conversations']} conversation(s) and "
                f"{stats['messages']} message(s) across {stats['matters']} "
                f"closed matter(s)."
            )
        )
