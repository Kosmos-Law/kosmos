from django.db import migrations, models


def turn_reports_off(apps, schema_editor):
    """Until now the Reports permission did nothing: every report also
    required the staff flag, which only the server's command line sets. So
    nobody was ever given the permission on purpose, yet every user has it,
    because it defaulted to on. The reports now open on the permission
    alone, and it has to start from off, or this release would show the
    firm's revenue to everyone. Administrators are not affected: they do not
    need the permission."""
    CustomUser = apps.get_model("accounts", "CustomUser")
    CustomUser.objects.exclude(role="ADMIN").update(perm_reports=False)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0016_emailverificationcode_attempts"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="perm_reports",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="historicalcustomuser",
            name="perm_reports",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(turn_reports_off, migrations.RunPython.noop),
    ]
