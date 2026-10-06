# Second half of the agenda retirement (see 0092): drop the column once the
# rows that used it are gone and their deferred checks have committed.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('case', '0092_remove_agenda_and_auto_threads'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='conversation',
            name='agenda_user',
        ),
        migrations.RemoveField(
            model_name='historicalconversation',
            name='agenda_user',
        ),
    ]
