# Google Contacts becomes per user (2026-10-28): each user connects their
# own Google account and copies contacts to it. See
# docs/decisions/2026-10-28-google-calendar-removed-contacts-per-user.md.
# Contact.google_id, the one copy in the firm-wide account, becomes a
# GoogleContactCopy held by no one, so the link survives until
# `manage.py adopt_google_contacts <username>` gives it to the user who
# owns that account.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def keep_copies(apps, schema_editor):
    Contact = apps.get_model("contacts", "Contact")
    GoogleContactCopy = apps.get_model("contacts", "GoogleContactCopy")
    copies = [
        GoogleContactCopy(contact_id=pk, user=None, resource_name=google_id)
        for pk, google_id in Contact.objects.exclude(google_id__isnull=True)
        .exclude(google_id="")
        .values_list("pk", "google_id")
    ]
    GoogleContactCopy.objects.bulk_create(copies)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contacts", "0010_contact_user_set_null"),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleContactCopy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("resource_name", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="google_copies",
                        to="contacts.contact",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="google_contact_copies",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "app_contact_google_copy",
            },
        ),
        migrations.AddConstraint(
            model_name="googlecontactcopy",
            constraint=models.UniqueConstraint(
                fields=("contact", "user"), name="google_copy_once_per_user"
            ),
        ),
        migrations.RunPython(keep_copies, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="contact",
            name="google_id",
        ),
        migrations.RemoveField(
            model_name="historicalcontact",
            name="google_id",
        ),
    ]
