from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0022_user_show_pinned_tasks"),
    ]

    operations = [
        migrations.RenameField(
            model_name="customuser",
            old_name="show_pinned_tasks",
            new_name="show_assigned_tasks",
        ),
        migrations.RenameField(
            model_name="historicalcustomuser",
            old_name="show_pinned_tasks",
            new_name="show_assigned_tasks",
        ),
    ]
