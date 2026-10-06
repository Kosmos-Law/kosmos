from django.apps import apps
from django.contrib import admin

from apps.settings.models import Firm


@admin.register(Firm)
class FirmAdmin(admin.ModelAdmin):
    # Encrypted AI keys are managed under Settings > Integrations only.
    exclude = ("gemini_api_key", "anthropic_api_key")


models = apps.get_app_config("settings").get_models()

for model in models:
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
