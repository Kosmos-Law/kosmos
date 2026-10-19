"""Draft links (a conversation pinned to a Drive ODT) and the LibreOffice
companion's setup modal, .oxt download and token-authed JSON API. The paths
keep their historic /case/ prefix: the installed companion extension polls
/case/drafts/companion/api/.
"""

from django.contrib.auth.decorators import login_required
from django.urls import path

from apps.drafts import companion, views

app_name = "drafts"

urlpatterns = [
    # Draft links (a conversation pinned to a Drive ODT; edits apply via
    # the LibreOffice companion)
    path(
        "case/ai/conversations/<int:conv_id>/draft/picker/",
        views.draft_picker,
        name="picker",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/draft/link/",
        views.draft_link,
        name="link",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/draft/unlink/",
        views.draft_unlink,
        name="unlink",
    ),
    path(
        "case/ai/conversations/<int:conv_id>/draft/chip/",
        views.draft_chip,
        name="chip",
    ),
    # LibreOffice companion: setup modal + personalized .oxt (browser,
    # logged-in) and the token-authed JSON API the extension polls.
    path(
        "case/drafts/companion/setup/",
        views.draft_companion_setup,
        name="companion-setup",
    ),
    path(
        "case/drafts/companion/kosmos-companion.oxt",
        login_required(companion.companion_oxt),
        name="companion-oxt",
    ),
    path(
        "case/drafts/companion/api/sessions/",
        companion.api_sessions,
        name="companion-api-sessions",
    ),
    path(
        "case/drafts/companion/api/<int:link_id>/hello/",
        companion.api_hello,
        name="companion-api-hello",
    ),
    path(
        "case/drafts/companion/api/<int:link_id>/ops/",
        companion.api_ops,
        name="companion-api-ops",
    ),
    path(
        "case/drafts/companion/api/<int:link_id>/rounds/<int:round_id>/",
        companion.api_result,
        name="companion-api-result",
    ),
]
