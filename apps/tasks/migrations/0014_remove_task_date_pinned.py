from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0013_task_date_pinned"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="historicaltask",
            name="date_pinned",
        ),
        migrations.RemoveField(
            model_name="task",
            name="date_pinned",
        ),
    ]
