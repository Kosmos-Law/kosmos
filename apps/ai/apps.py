from django.apps import AppConfig


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai"
    label = "ai"

    def ready(self):
        from apps.accounts.access import register_matter_lookup
        from apps.ai.models import Conversation, Message

        # The conversation operations the intake chat's templates use
        # (apps/ai/views.py) resolve their matter through these.
        register_matter_lookup("conv_id", Conversation, ("matter_id",))
        register_matter_lookup("message_id", Message, ("conversation__matter_id",))
