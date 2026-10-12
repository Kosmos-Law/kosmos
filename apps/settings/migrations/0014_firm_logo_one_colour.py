from django.db import migrations, models


def refresh_existing_logo(apps, schema_editor):
    """Work out the facts for a logo uploaded before they existed. A logo
    that can't be read is left as it was: re-uploading it does the same."""
    from apps.settings.logo import refresh_logo_facts

    Firm = apps.get_model("settings", "Firm")
    for firm in Firm.objects.exclude(logo="").exclude(logo=None):
        try:
            refresh_logo_facts(firm)
        except Exception:  # noqa: BLE001
            pass


class Migration(migrations.Migration):
    dependencies = [
        ("settings", "0013_remove_firm_logo_dark"),
    ]

    operations = [
        migrations.AddField(
            model_name="firm",
            name="logo_one_colour",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name="firm",
            name="logo_print",
            field=models.ImageField(
                blank=True, editable=False, null=True, upload_to="company/"
            ),
        ),
        migrations.RunPython(refresh_existing_logo, migrations.RunPython.noop),
    ]
