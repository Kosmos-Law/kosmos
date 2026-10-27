# The Google Drive integration was removed on 2026-10-27 (the firm's files
# moved to Dropbox): see docs/decisions/2026-10-27-google-drive-removed.md.
# This drops the mirror's tables (folder mappings, per-matter state,
# tombstones, the sync cursor) and deletes the two Django-Q schedules, or
# qcluster would keep trying to import the deleted sync functions.
# Documents that came in from Drive stay; case 0097 drops their Drive
# columns, including the foreign key to DriveFolderMapping, so it runs first.

from django.db import migrations

RETIRED_SCHEDULES = ("drive-sync", "drive-sync-nightly-full")


def delete_schedules(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name__in=RETIRED_SCHEDULES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("drive", "0004_convert_legacy_links"),
        ("case", "0097_remove_document_drive_fields"),
        ("matters", "0057_remove_matter_drive_folder"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(delete_schedules, migrations.RunPython.noop),
        migrations.RemoveField(model_name="drivefoldermapping", name="matter"),
        migrations.RemoveField(model_name="drivefoldermapping", name="proceeding"),
        migrations.RemoveField(model_name="drivematterstate", name="matter"),
        migrations.DeleteModel(name="DriveRecordTombstone"),
        migrations.DeleteModel(name="DriveSyncState"),
        migrations.DeleteModel(name="DriveFolderMapping"),
        migrations.DeleteModel(name="DriveMatterState"),
    ]
