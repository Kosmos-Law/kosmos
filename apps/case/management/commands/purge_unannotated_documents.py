"""Delete documents nobody has worked on.

A document counts as worked on when it has a highlight, is cited by a
timeline fact, is referenced by a (retired) note, or is the PDF of a
promoted email. Everything else is deleted: the row, its stored file
(django-cleanup), its semantic-index chunks and its search entry, the
same as deleting it from the Documents tab. Labels, descriptions,
categories and proceedings do not protect a document.

Written for the Google Drive removal (2026-10-27), when most documents
were unannotated copies the mirror had brought in. Dry run by default;
pass --apply to delete.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Exists, OuterRef

from apps.case.models import Document, Fact, Highlight


def unannotated_documents():
    """Documents with no highlight, fact, note or promoted email."""
    facts = Fact.documents.through.objects.filter(document_id=OuterRef("pk"))
    notes = Document.notes.through.objects.filter(document_id=OuterRef("pk"))
    return (
        Document.objects.exclude(
            Exists(Highlight.objects.filter(document_id=OuterRef("pk")))
        )
        .exclude(Exists(facts))
        .exclude(Exists(notes))
        .filter(source_emails__isnull=True)
    )


class Command(BaseCommand):
    help = (
        "Delete documents that have no highlight, fact, note or promoted "
        "email, with their stored files. Dry run unless --apply is given."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true", help="Delete; without it, only report"
        )
        parser.add_argument("--matter", type=int, help="Restrict to one matter id")
        parser.add_argument(
            "--list", action="store_true", help="Name every document, not just counts"
        )

    def handle(self, *args, **options):
        docs = unannotated_documents()
        if options["matter"]:
            docs = docs.filter(matter_id=options["matter"])

        per_matter = (
            docs.values("matter_id", "matter__name")
            .annotate(n=Count("pk"))
            .order_by("matter__name")
        )
        total = 0
        for row in per_matter:
            total += row["n"]
            self.stdout.write(
                f"Matter {row['matter_id']} ({row['matter__name']}): {row['n']}"
            )
            if options["list"]:
                for d in docs.filter(matter_id=row["matter_id"]).order_by("pk"):
                    self.stdout.write(f"  #{d.pk} {d.name} [{d.category}]")

        kept = (
            Document.objects.count() - docs.count() if not options["matter"] else None
        )
        summary = f"\n{total} unannotated document(s)"
        if kept is not None:
            summary += f"; {kept} annotated document(s) stay"
        self.stdout.write(summary + ".")

        if not options["apply"]:
            self.stdout.write("Dry run; pass --apply to delete.")
            return

        removed = 0
        # One at a time, so each delete runs the same signals as the
        # Documents tab's Delete (file, semantic chunks, search entry).
        for pk in list(docs.values_list("pk", flat=True)):
            document = Document.objects.filter(pk=pk).first()
            if document is not None:
                document.delete()
                removed += 1
        self.stdout.write(self.style.SUCCESS(f"Removed {removed} document(s)."))
