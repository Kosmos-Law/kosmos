"""Backfill the semantic material index (apps/case/semantic.py).

Embeds every open matter's materials of every registered kind (documents,
emails, highlights and timeline facts).
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
        matters = Matter.objects.filter(status="Open")
        if options["matter"]:
            matters = Matter.objects.filter(id=options["matter"])
        for matter in matters:
            self.stdout.write(f"Indexing {matter.name} ({matter.id})...")
            for entry in kinds:
                if entry.backfill:
                    run(entry.kind, entry.backfill(matter))
        self.stdout.write(
            self.style.SUCCESS(
                f"Indexed {totals['objects']} objects, {totals['chunks']} chunks "
                "written (unchanged objects skipped)."
            )
        )
