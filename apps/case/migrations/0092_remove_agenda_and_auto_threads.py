# The dash Plan chat (agenda) and the nightly Auto Summary / Auto Agenda
# threads were retired on 2026-10-06. Their conversations go with them: the
# agenda chats have no owner field left to hang on, and the auto threads are
# ai_context="always", so left behind they would feed every case chat a
# summary that never refreshes again. Their Django-Q schedules go too, or
# qcluster would keep trying to import the deleted functions.
#
# The agenda_user column is dropped in 0093, not here: Postgres refuses an
# ALTER TABLE in the same transaction as row deletes whose deferred
# foreign-key checks are still pending.

from django.db import migrations

RETIRED_SCHEDULES = (
    "auto-summary-nightly",
    "auto-summary-weekly-rebuild",
    "auto-daily-plan",
)


def delete_retired(apps, schema_editor):
    Conversation = apps.get_model("case", "Conversation")
    Schedule = apps.get_model("django_q", "Schedule")
    Conversation.objects.filter(agenda_user__isnull=False).delete()
    # The auto threads are the only matter conversations with no user.
    Conversation.objects.filter(
        matter__isnull=False,
        user__isnull=True,
        title__in=("Auto Summary", "Auto Agenda"),
    ).delete()
    Schedule.objects.filter(name__in=RETIRED_SCHEDULES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('case', '0091_remove_conversation_effort'),
        ('django_q', '0018_task_success_index'),
    ]

    operations = [
        migrations.RunPython(delete_retired, migrations.RunPython.noop),
    ]
