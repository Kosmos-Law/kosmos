"""Remove intake notes left behind by intakes deleted before the delete view
removed their notes (Note.intake is SET_NULL, so the database only detached
them, and no screen can reach a note with no intake)."""

from django.core.management.base import BaseCommand

from apps.intakes.models import Note


class Command(BaseCommand):
    help = (
        "List intake notes whose intake is gone, and with --apply delete "
        "them. Reports only by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Delete the listed notes. Without this nothing is changed.",
        )

    def handle(self, *args, **options):
        orphans = Note.objects.filter(intake__isnull=True).order_by("id")

        for note in orphans:
            self.stdout.write(
                f"  ORPHAN  ID={note.id}  {note.date or '(no date)'}  "
                f"{note.type or '(no type)'}"
            )

        count = orphans.count()
        if not count:
            self.stdout.write(self.style.SUCCESS("No orphan intake notes found."))
            return

        self.stdout.write(f"\nFound {count} orphan intake note(s).")

        if not options["apply"]:
            self.stdout.write("Nothing deleted. Run again with --apply to delete.")
            return

        orphans.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} orphan note(s)."))
