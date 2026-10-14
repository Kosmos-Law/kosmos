# Tasks handed over before the assignor was recorded: the creator stands
# in, so firm due dates apply to the hand-offs already on people's lists.
# Its own migration (not the AddField's) so the UPDATE runs after the
# ALTER has committed.

from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    Task = apps.get_model("tasks", "Task")
    Task.objects.filter(
        assigned_by__isnull=True, created_by__isnull=False, user__isnull=False
    ).exclude(user=F("created_by")).update(assigned_by=F("created_by"))


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0012_task_assigned_by"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
