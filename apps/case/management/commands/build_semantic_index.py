"""Backfill the semantic material index (apps/case/semantic.py).

Embeds every open matter's materials of every registered kind (documents,
notes, emails, highlights and timeline facts), plus the firm library.
Unchanged objects (same content hash) are skipped, so re-runs are cheap;
run once after deploy and whenever the index needs a catch-up (for
example after qcluster downtime).
"""

from django.core.management.base import BaseCommand

from apps.case import semantic
from apps.matters.models import Matter


class Command(BaseCommand):
    help = "Embed matter materials for semantic search"

    def add_arguments(self, parser):
        parser.add_argument("--matter", type=int, help="One matter id only")
        parser.add_argument("--library", action="store_true", help="Library notes only")

    def handle(self, *args, **options):
        totals = {"objects": 0, "chunks": 0}

        def run(kind, queryset):
            for obj in queryset.iterator():
                chunks = semantic.index_object(kind, obj)
                totals["objects"] += 1
                totals["chunks"] += chunks
                if totals["objects"] % 100 == 0:
                    self.stdout.write(
                        f"  ...{totals['objects']} objects, "
                        f"{totals['chunks']} chunks so far"
                    )

        kinds = semantic.kinds()
        if not options["library"]:
            matters = Matter.objects.filter(status="Open")
            if options["matter"]:
                matters = Matter.objects.filter(id=options["matter"])
            for matter in matters:
                self.stdout.write(f"Indexing {matter.name} ({matter.id})...")
                for entry in kinds:
                    if entry.backfill:
                        run(entry.kind, entry.backfill(matter))
        if not options["matter"]:
            self.stdout.write("Indexing the firm library...")
            for entry in kinds:
                if entry.backfill_library:
                    run(entry.kind, entry.backfill_library())
        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {totals['objects']} objects, {totals['chunks']} chunks "
                "written (unchanged objects skipped)."
            )
        )
