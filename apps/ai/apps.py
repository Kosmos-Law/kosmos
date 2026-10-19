from django.apps import AppConfig


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai"
    label = "ai"

    def ready(self):
        from apps.accounts.access import register_matter_lookup
        from apps.ai.models import Conversation, Message
        from apps.ai.views import get_conversation_list_context
        from apps.case.services import Tab, register_tab
        from apps.settings.ai import ai_enabled

        # The AI tab of the case shell, once a provider is set up. Saved
        # case law is a view inside it, so the tab lights for it too.
        register_tab(
            Tab(
                name="ai",
                label="AI",
                index_url="ai:index",
                list_url="ai:list",
                template="ai/list.html",
                data=get_conversation_list_context,
                order=90,
                available=lambda user, matter_id: ai_enabled(),
                also_active=("caselaws",),
                wrapper_id="ai-conversations",
                refresh_trigger="conversationsChanged from:body",
            )
        )
        register_matter_lookup("conv_id", Conversation, ("matter_id",))
        register_matter_lookup("message_id", Message, ("conversation__matter_id",))
