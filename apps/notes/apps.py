from django.apps import AppConfig


class NotesConfig(AppConfig):
    """Retired. The notes feature (the Library and the case file's Notes
    tab) was removed on 2026-10-27; only the models and migrations stay,
    so the existing rows are kept and Django still cascades them when a
    matter or user is deleted. Nothing reads or writes them. A later
    migration can drop the tables. See
    docs/decisions/2026-10-27-notes-retired.md."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notes"
