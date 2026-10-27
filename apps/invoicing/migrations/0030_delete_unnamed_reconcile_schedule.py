# An older setup left an unnamed daily Django-Q schedule for
# apps.invoicing.pay.reconcile.poll_pending. The named "payments-reconcile"
# schedule (apps/management/schedules.py) runs the same function hourly, so
# the unnamed one only reran it once a day. Delete it.

from django.db import migrations


def delete_unnamed(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(
        name__isnull=True, func="apps.invoicing.pay.reconcile.poll_pending"
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("invoicing", "0029_transmission_request_provenance"),
        ("django_q", "0018_task_success_index"),
    ]

    operations = [
        migrations.RunPython(delete_unnamed, migrations.RunPython.noop),
    ]
