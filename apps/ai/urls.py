"""Routes of the AI app: the matter chat under /case/<id>/ai/, the
conversation operations under /case/ai/, and the token-authed JSON API the
Claude Desktop MCP server calls under /case/api/. The paths keep their
historic /case/ prefix so bookmarks, the MCP client and the permission
middleware's patterns go on working; only the URL names moved to the
``ai`` namespace.
"""

from django.urls import path

from apps.ai import api, sessions, views

app_name = "ai"

urlpatterns = [
    # Token-authed JSON API for the Claude Desktop MCP server. The
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
    # AI Chat (matter-scoped)
    path("case/<int:matter_id>/ai/", sessions.sessions_index, name="index"),
    path("case/<int:matter_id>/ai/list/", sessions.sessions_list, name="list"),
    path(
        "case/<int:matter_id>/ai/sessions/launch/",
        sessions.session_launch,
        name="session-launch",
    ),
    path(
        "case/ai/sessions/<int:session_id>/",
        sessions.session_page,
        name="session-page",
    ),
    path(
        "case/ai/sessions/<int:session_id>/messages/",
        sessions.session_messages,
        name="session-messages",
    ),
    path(
        "case/ai/sessions/<int:session_id>/send/",
        sessions.session_send,
        name="session-send",
    ),
    path(
        "case/ai/sessions/<int:session_id>/model/",
        sessions.session_model,
        name="session-model",
    ),
    path(
        "case/ai/sessions/<int:session_id>/rename/",
        sessions.session_rename,
        name="session-rename",
    ),
    path(
        "case/ai/sessions/<int:session_id>/delete/",
        sessions.session_delete,
        name="session-delete",
    ),
    # The archive: conversations from the chat that preceded sessions.
    path("case/<int:matter_id>/ai/archive/", views.ai_index, name="archive"),
    path("case/<int:matter_id>/ai/archive/list/", views.ai_list, name="archive-list"),
    path("case/<int:matter_id>/ai/sort/<str:order>/", views.ai_sort, name="sort"),
    path("case/<int:matter_id>/ai/filter/", views.ai_filter, name="filter"),
    path("case/<int:matter_id>/ai/messages/", views.message_list, name="messages"),
    path("case/<int:matter_id>/ai/send/", views.send_message, name="send"),
    path(
        "case/<int:matter_id>/ai/conversations/",
        views.conversation_list,
        name="conversations",
    ),
    path(
        "case/<int:matter_id>/ai/conversations/new/",
        views.new_conversation_view,
        name="new-conversation-view",
    ),
    path(
        "case/<int:matter_id>/ai/conversations/new/prompt/",
        views.new_conversation_prompt,
        name="new-conversation-prompt",
    ),
    path(
        "case/<int:matter_id>/ai/prompt-editor/",
        views.prompt_editor_modal,
        name="prompt-editor",
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
    path(
        "case/ai/conversations/<int:conv_id>/",
        views.select_conversation,
        name="select-conversation",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/view/",
        views.conversation_view,
        name="conversation-view",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/delete/",
        views.delete_conversation,
        name="delete-conversation",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/clone/",
        views.clone_conversation,
        name="clone-conversation",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/append-form/",
        views.append_conversation_form,
        name="append-form",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/append/",
        views.append_conversation,
        name="append-conversation",
    ),
    path(
        "case/ai/messages/<int:message_id>/split/",
        views.split_conversation,
        name="split-conversation",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/set-ai/<str:state>/",
        views.set_ai_context,
        name="set-ai-context",
    ),
    path(
        "case/ai/messages/<int:message_id>/vetting-status/",
        views.message_vetting_status,
        name="message-vetting-status",
    ),
    path(
        "case/ai/messages/<int:message_id>/citation/<int:citation_index>/vetting/",
        views.citation_vetting_detail,
        name="citation-vetting-detail",
    ),
    # AI conversation selection & bulk actions
    path(
        "case/<int:matter_id>/ai/toggle-select/<int:conv_id>/",
        views.ai_toggle_select,
        name="toggle-select",
    ),
    path(
        "case/<int:matter_id>/ai/select-all/",
        views.ai_select_all,
        name="select-all",
    ),
    path(
        "case/<int:matter_id>/ai/clear-selection/",
        views.ai_clear_selection,
        name="clear-selection",
    ),
    path(
        "case/<int:matter_id>/ai/bulk-set-context/<str:state>/",
        views.ai_bulk_set_context,
        name="bulk-set-context",
    ),
    path(
        "case/<int:matter_id>/ai/bulk-delete/",
        views.ai_bulk_delete,
        name="bulk-delete",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/rename/",
        views.rename_conversation,
        name="rename-conversation",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/rename-form/",
        views.rename_form,
        name="rename-form",
    ),
]
