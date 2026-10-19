from django.apps import AppConfig


class MailConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.mail"

    def ready(self):
        from watson import search as watson

        from apps.accounts.access import register_matter_lookup
        from apps.case.services import Tab, register_semantic_kind, register_tab
        from apps.mail.google import emails_tab_available
        from apps.mail.models import Email
        from apps.mail.views import get_emails_data
        from apps.management.watson import TruncatingSearchAdapter

        # The Emails tab of the case shell. Hidden on a server without
        # Google sign-in unless the matter already holds synced emails.
        register_tab(
            Tab(
                name="emails",
                label="Emails",
                index_url="mail:emails-index",
                list_url="mail:emails-list",
                template="mail/list.html",
                data=lambda request, matter: get_emails_data(
                    request, matter, matter.id
                ),
                order=60,
                available=lambda user, matter_id: (
                    matter_id is None or emails_tab_available(matter_id)
                ),
            )
        )
        register_matter_lookup("email_id", Email, ("matter_id",))

        def email_source(email):
            if email.ai_context == "never":
                return email.matter_id, ""
            return email.matter_id, (
                f"{email.subject or ''}\nFrom: {email.sender or ''}\n"
                f"{email.body_text or ''}"
            )

        register_semantic_kind(
            "email",
            Email,
            email_source,
            backfill=lambda matter: Email.objects.filter(matter=matter).dedup(),
        )
        # Keyword search (the agent's search_materials); synced rows are
        # created one at a time, so watson's save signal indexes them.
        # Existing rows need one `manage.py buildwatson` after deploy.
        watson.register(
            Email,
            adapter_cls=TruncatingSearchAdapter,
            fields=("subject", "body_text", "sender"),
        )
