"""Views for a case AI conversation's draft link.

Linking a new draft is off until the files have a home the server can
list (it used to be a picker over the matter's Google Drive folder; see
docs/decisions/2026-10-27-google-drive-removed.md). An existing link shows
in the chat composer's chip and can be unlinked; the companion setup modal
(extension download) stays for users of existing links.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.accounts.models import ApiToken
from apps.ai.models import Conversation
from apps.drafts.companion import EXTENSION_VERSION


def _get_conversation(conv_id):
    """A matter conversation. Membership of its matter is checked centrally
    from the URL; an intake chat (no matter, so that check passes it) has
    no drafts and is not found here."""
    return get_object_or_404(
        Conversation.objects.select_related("matter"),
        pk=conv_id,
        matter__isnull=False,
    )


def _chip_response(request, conversation):
    response = render(
        request,
        "ai/draft-chip.html",
        {"conversation": conversation, "matter": conversation.matter},
    )
    response["HX-Trigger"] = "draftLinkChanged"
    return response


@login_required
@require_http_methods(["POST"])
def draft_unlink(request, conv_id):
    """Remove the conversation's draft link (the document is untouched)."""
    conversation = _get_conversation(conv_id)
    link = getattr(conversation, "draft_link", None)
    if link is not None:
        link.delete()
        conversation.refresh_from_db()
    return _chip_response(request, conversation)


@login_required
def draft_chip(request, conv_id):
    """The chip partial, fetched once a new conversation's row exists."""
    conversation = _get_conversation(conv_id)
    return render(
        request,
        "ai/draft-chip.html",
        {"conversation": conversation, "matter": conversation.matter},
    )


@login_required
def draft_companion_setup(request):
    """Modal with the personalized extension download and install steps."""
    return render(
        request,
        "ai/companion-setup.html",
        {
            "token": ApiToken.for_user(request.user),
            "extension_version": EXTENSION_VERSION,
        },
    )
