from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("settings", "0012_firm_logo_dark_email"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="firm",
            name="logo_dark",
        ),
    ]
