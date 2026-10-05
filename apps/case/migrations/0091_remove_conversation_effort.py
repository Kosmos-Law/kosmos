# Conversation.effort was dead: the effort tiers were pruned on 2026-08-14
# and no run read it since (clone and split only copied it along).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('case', '0090_fable51_picker'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='conversation',
            name='effort',
        ),
        migrations.RemoveField(
            model_name='historicalconversation',
            name='effort',
        ),
    ]
