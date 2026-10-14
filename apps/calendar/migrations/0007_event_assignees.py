# An event's assignee becomes a set (Event.assignees). The old one-to-many
# column is carried into the set here and dropped in 0008, in a migration
# of its own, so the row copies and the ALTER never share a transaction.

from django.conf import settings
from django.db import migrations, models


def copy_assignee(apps, schema_editor):
    Event = apps.get_model("calendar", "Event")
    for event in Event.objects.exclude(assigned_to=None).only("id", "assigned_to"):
        event.assignees.add(event.assigned_to_id)


class Migration(migrations.Migration):
    dependencies = [
        ("calendar", "0006_notifications_and_end_date"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="assignees",
            field=models.ManyToManyField(
                blank=True, related_name="assigned_events", to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.RunPython(copy_assignee, migrations.RunPython.noop),
    ]
