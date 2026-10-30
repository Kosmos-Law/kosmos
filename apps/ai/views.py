"""The views the intake chat's message templates still call: a
reply's status and cancel, deleting a message, and citation vetting.
The matter chat itself is retired (docs/decisions/2026-10-30-ai-chat-retired.md)."""

import logging
import time

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.llm.status import status_cache

from .access import accessible_matters, conversation_for_user
from .models import Message

logger = logging.getLogger(__name__)


def _error_reply(message):
    """The chat message shown for a failed run. Some workers already lead
    their message with "Error:"; it is said once."""
    detail = str(message or "").strip()
    if detail.lower().startswith("error:"):
        detail = detail[len("error:") :].strip()
    return f"Error: Unable to get response. {detail}".strip()


def _terminal(response):
    """Mark a status-poll response as the poller's last.

    status.html polls itself with hx-swap="morph" (idiomorph), and the
    protocol ends the every-1s interval by answering with a DIFFERENT
    root element, which morph replaces rather than patches. That only
    holds where idiomorph is loaded; without it htmx falls back to
    innerHTML, the reply lands INSIDE the indicator, and the interval
    runs on (2026-08-23: the intake chat window). HX-Reswap forces an
    outerHTML replacement of the poller whatever the page's swap
    support, so a terminal answer always takes the poller with it.
    """
    response["HX-Reswap"] = "outerHTML"
    return response


def _poll_ended():
    """Empty terminal response: an empty div under a DIFFERENT id than the
    poller, so a morph swap replaces the element (a same-id root would be
    patched in place, keeping its interval alive), plus HX-Reswap for
    pages without morph."""
    return _terminal(HttpResponse('<div id="ai-status-ended"></div>'))


@login_required
def ai_status(request, conv_id):
    """The status poll of a running chat turn: the intake chat's, the one
    chat left. Reads the run's entry in the status cache and, when it is
    finished, writes the answer as a message."""
    # An intake chat names no matter, so the central matter check never
    # sees it; access.conversation_for_user checks the Intakes permission.
    conversation = conversation_for_user(conv_id, request.user)

    cache_key = f"ai_status_{conv_id}"
    status_data = status_cache.get(cache_key)
    if status_data is None:
        # send_message seeds this entry before spawning the worker thread,
        # and the thread's heartbeat keeps re-touching it while its
        # process is alive (see status.py). A missing entry while an
        # indicator is still polling therefore means the run died with
        # its process (deploy, reload, crash) and the entry expired. Say
        # so plainly instead of polling "Checking..." forever.
        #
        # But only when a reply is actually outstanding, i.e. the latest
        # message is the user's. A poll that lands after the reply (or
        # an earlier interruption note) was already written must not add
        # another: a poller that outlived its swap (2026-08-23, the intake
        # window lacked idiomorph, so "morph" fell back to innerHTML and
        # the indicator never went away) wrote one of these per second.
        latest = conversation.messages.order_by("-created_at").first()
        if latest is None or latest.role != "user":
            return _poll_ended()
        interrupted = Message.objects.create(
            conversation=conversation,
            role="assistant",
            content=(
                "This request was interrupted before it finished (the "
                "server restarted mid-run). Please re-send your message."
            ),
        )
        return _terminal(
            render(request, "ai/message-single.html", {"message": interrupted})
        )

    if status_data["status"] == "complete":
        # Get verified citations from status data
        verified_citations = status_data.get("citations", [])
        logger.info(
            "Retrieved %d citations from cache for conversation %s",
            len(verified_citations),
            conv_id,
        )

        # Save assistant message with citations (research-kind payloads also
        # carry the research trail; classic payloads lack the key -> []).
        assistant_message = Message.objects.create(
            conversation=conversation,
            role="assistant",
            content=status_data["response"],
            input_tokens=status_data.get("input_tokens"),
            output_tokens=status_data.get("output_tokens"),
            verified_citations=verified_citations,
            activity_log=status_data.get("activity_log", []),
        )

        # Update conversation timestamp
        conversation.save()

        # Clear the cache
        status_cache.delete(cache_key)

        # Return just the new assistant message (replaces status indicator).
        return _terminal(
            render(request, "ai/message-single.html", {"message": assistant_message})
        )

    if status_data["status"] == "error":
        # Save error as assistant message
        error_message = Message.objects.create(
            conversation=conversation,
            role="assistant",
            content=_error_reply(status_data["message"]),
            activity_log=status_data.get("activity_log", []),
        )

        # Clear the cache
        status_cache.delete(cache_key)

        # Return just the error message (replaces status indicator)
        return _terminal(
            render(request, "ai/message-single.html", {"message": error_message})
        )

    if status_data["status"] == "cancelled":
        # Keep cache entry (don't delete) so background thread's
        # is_cancelled() check continues to see "cancelled" status.
        return _poll_ended()

    # Calculate elapsed time if available
    elapsed_seconds = None
    if "started_at" in status_data:
        elapsed_seconds = int(time.time() - status_data["started_at"])

    # Still processing - return status indicator with continued polling.
    return render(
        request,
        "ai/status.html",
        {
            "status": status_data["status"],
            "message": status_data["message"],
            "conversation": conversation,
            "elapsed_seconds": elapsed_seconds,
            "activity_log": status_data.get("activity_log"),
        },
    )


@login_required
def cancel_request(request, conv_id):
    """Cancel an in-progress AI request."""
    # Same check as ai_status: cancelling deletes the pending question.
    conversation = conversation_for_user(conv_id, request.user)

    if request.method != "POST":
        return HttpResponse(status=405)

    cache_key = f"ai_status_{conv_id}"
    status_data = status_cache.get(cache_key)

    if status_data and status_data.get("status") not in (
        "complete",
        "error",
        "cancelled",
    ):
        # Set cancelled status
        status_cache.set(
            cache_key,
            {
                "status": "cancelled",
                "message": "Request cancelled",
            },
            timeout=60,
        )

        # Delete the pending user message (last message if it's from user with no response)
        last_message = conversation.messages.order_by("-created_at").first()
        if last_message and last_message.role == "user":
            last_message.delete()

    # Return empty indicator (no polling) and trigger message list refresh.
    return HttpResponse(
        '<div id="ai-status-indicator"></div>',
        headers={"HX-Trigger": "messagesUpdated"},
    )


@login_required
def delete_message(request, message_id):
    """Delete a message pair (user question + assistant response)."""
    message = get_object_or_404(
        Message,
        pk=message_id,
        conversation__matter__in=accessible_matters(request.user),
    )
    conversation = message.conversation

    if request.method != "POST":
        return HttpResponse(status=405)

    if message.role != "user":
        return HttpResponse("Can only delete user messages", status=403)

    # Delete the following assistant message if it exists
    next_message = (
        conversation.messages.filter(created_at__gt=message.created_at)
        .order_by("created_at")
        .first()
    )
    if next_message and next_message.role == "assistant":
        next_message.delete()
    message.delete()

    # Trigger messagesUpdated event to refresh the message list
    return HttpResponse(status=204, headers={"HX-Trigger": "messagesUpdated"})


@login_required
def citation_vetting_detail(request, message_id, citation_index):
    """Return a modal fragment describing the Flash vetting verdict for one citation."""
    message = get_object_or_404(
        Message,
        pk=message_id,
        conversation__matter__in=accessible_matters(request.user),
    )

    citations = message.verified_citations or []
    if citation_index < 0 or citation_index >= len(citations):
        return HttpResponse(status=404)

    citation = citations[citation_index]
    return render(
        request,
        "ai/citation-vetting-modal.html",
        {
            "citation": citation,
            "vetting": citation.get("vetting") or {},
            "message": message,
        },
    )


@login_required
def message_vetting_status(request, message_id):
    """Return the updated assistant message content with current vetting badges.

    The wrapping element advertises an HTMX poll trigger only while any case
    citation is still in a non-terminal vetting state; once everything is
    done, the fragment is returned without the trigger and polling stops.
    """
    message = get_object_or_404(
        Message,
        pk=message_id,
        conversation__matter__in=accessible_matters(request.user),
    )

    return render(request, "ai/vetting-wrapper.html", {"message": message})
