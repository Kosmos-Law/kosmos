from django.db import migrations
from django.utils import timezone

INACTIVE_STATUSES = ("Complete", "Closed")


def backfill_date_end(apps, schema_editor):
    """Give matters that are already closed out the closing date the
    application did not record: the day their current run of Complete or
    Closed began, read from their history. A matter with no such history
    keeps a blank date."""
    Matter = apps.get_model("matters", "Matter")
    HistoricalMatter = apps.get_model("matters", "HistoricalMatter")

    matters = Matter.objects.filter(
        status__in=INACTIVE_STATUSES, date_end__isnull=True
    )
    for matter_id in matters.values_list("id", flat=True):
        ended = None
        rows = (
            HistoricalMatter.objects.filter(id=matter_id)
            .order_by("-history_date")
            .values_list("status", "history_date")
        )
        for status, when in rows.iterator():
            if status not in INACTIVE_STATUSES:
                break
            ended = when
        if ended is not None:
            # .update(): no save(), so no history row and no model logic.
            Matter.objects.filter(pk=matter_id).update(
                date_end=timezone.localtime(ended).date()
            )


class Migration(migrations.Migration):
    dependencies = [
        ("matters", "0053_unlink_complete_matters"),
    ]

    operations = [
        migrations.RunPython(backfill_date_end, migrations.RunPython.noop),
    ]
