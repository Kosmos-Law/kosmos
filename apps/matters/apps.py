from django.apps import AppConfig


class MattersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.matters"

    def ready(self):
        from .system_rows import connect

        connect(self)
