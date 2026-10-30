"""Routes of the AI app: the token-authed JSON API over a matter under
/case/api/ (the MCP server in apps/mcp calls the same service functions
in-process), and the few conversation operations the intake chat's
message templates still use under /case/ai/. The paths keep their
historic /case/ prefix so scripts and the permission middleware's
patterns go on working.
"""

from django.urls import path

from apps.ai import api, views

app_name = "ai"

urlpatterns = [
    # Token-authed JSON API over a matter. The
    # facts/witnesses/emails/conversations routes must precede the
    # <str:section> catch-all so their POST/extra-segment forms match first.
    path("case/api/matters/", api.api_matters, name="api-matters"),
    path(
        "case/api/matter/<int:matter_id>/facts/",
        api.api_matter_facts,
        name="api-matter-facts",
    ),
    path(
        "case/api/matter/<int:matter_id>/witnesses/",
        api.api_matter_witnesses,
        name="api-matter-witnesses",
    ),
    path(
        "case/api/matter/<int:matter_id>/emails/<str:thread_id>/",
        api.api_email_thread,
        name="api-email-thread",
    ),
    path(
        "case/api/matter/<int:matter_id>/conversations/<int:conversation_id>/",
        api.api_conversation,
        name="api-conversation",
    ),
    path(
        "case/api/matter/<int:matter_id>/search/",
        api.api_search_materials,
        name="api-search-materials",
    ),
    path(
        "case/api/matter/<int:matter_id>/time/",
        api.api_matter_time,
        name="api-matter-time",
    ),
    path(
        "case/api/matter/<int:matter_id>/<str:section>/",
        api.api_matter_section,
        name="api-matter-section",
    ),
    path(
        "case/api/documents/<int:document_id>/",
        api.api_document,
        name="api-document",
    ),
    path(
        "case/api/invoices/<int:invoice_id>/",
        api.api_invoice,
        name="api-invoice",
    ),
    path(
        "case/api/tasks/",
        api.api_create_task,
        name="api-create-task",
    ),
    path(
        "case/api/tasks/<int:task_id>/complete/",
        api.api_complete_task,
        name="api-complete-task",
    ),
    path(
        "case/api/events/",
        api.api_create_event,
        name="api-create-event",
    ),
    path(
        "case/api/contacts/",
        api.api_create_contact,
        name="api-create-contact",
    ),
    # AI conversation operations
    path(
        "case/ai/status/<int:conv_id>/",
        views.ai_status,
        name="status",
    ),
    path(
        "case/ai/cancel/<int:conv_id>/",
        views.cancel_request,
        name="cancel",
    ),
    path(
        "case/ai/messages/<int:message_id>/delete/",
        views.delete_message,
        name="delete-message",
    ),
]
