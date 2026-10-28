# The Google Calendar sync was removed on 2026-10-28; Kosmos is the only
# place firm events are kept: see
# docs/decisions/2026-10-28-google-calendar-removed-contacts-per-user.md.
# This drops the sync cursor, the queue of deletions waiting to reach
# Google, and the two Event columns that tracked the Google copy, and
# deletes the calendar-sync schedule, or qcluster would keep trying to
# import the deleted sync function. The events themselves are untouched.

from django.db import migrations

RETIRED_SCHEDULES = ("calendar-sync",)


def delete_schedules(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name__in=RETIRED_SCHEDULES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("calendar", "0011_move_meeting_links"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(delete_schedules, migrations.RunPython.noop),
        migrations.DeleteModel(name="CalendarSyncState"),
        migrations.DeleteModel(name="PendingGoogleDeletion"),
        migrations.RemoveField(model_name="event", name="google_id"),
        migrations.RemoveField(model_name="event", name="google_synced_at"),
        migrations.RemoveField(model_name="historicalevent", name="google_id"),
        migrations.RemoveField(model_name="historicalevent", name="google_synced_at"),
    ]
