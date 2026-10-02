"""Remove document records whose files are missing from storage."""

from django.core.management.base import BaseCommand
from django.db import connection

from apps.case.models import Document, Highlight


class Command(BaseCommand):
    help = (
        "List document records whose files are missing from storage, and "
        "with --apply delete them (and their highlights). Reports only by "
        "default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Delete the listed records. Without this nothing is changed.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List without deleting. This is the default; kept for old habits.",
        )

    def _clear_outline_references(self, highlight_ids):
        """Remove references from a legacy outlines table that lacks CASCADE.
        The table is left over from a removed app and exists only in databases
        old enough to have had it, so check before touching it."""
        if not highlight_ids:
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('outlines_outlineitem_highlights')")
            if cursor.fetchone()[0] is None:
                return
            cursor.execute(
                "DELETE FROM outlines_outlineitem_highlights "
                "WHERE highlight_id = ANY(%s)",
                [list(highlight_ids)],
            )

    def handle(self, *args, **options):
        apply = options["apply"] and not options["dry_run"]
        orphans = []

        for doc in Document.objects.all().order_by("id"):
            try:
                exists = bool(doc.file) and doc.file.storage.exists(doc.file.name)
            except Exception:
                exists = False

            if not exists:
                orphans.append(doc)
                self.stdout.write(f"  ORPHAN  ID={doc.id}  {doc.file.name}")

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No orphan documents found."))
            return

        self.stdout.write(f"\nFound {len(orphans)} orphan document(s).")

        if not apply:
            self.stdout.write("Nothing deleted. Run again with --apply to delete.")
            return

        orphan_ids = [doc.id for doc in orphans]

        # Clear outline references to highlights on these documents
        highlight_ids = set(
            Highlight.objects.filter(document_id__in=orphan_ids).values_list(
                "id", flat=True
            )
        )
        self._clear_outline_references(highlight_ids)

        # Delete highlights, then documents
        Highlight.objects.filter(document_id__in=orphan_ids).delete()
        count = Document.objects.filter(id__in=orphan_ids).delete()[0]

        self.stdout.write(self.style.SUCCESS(f"Deleted {count} record(s)."))
