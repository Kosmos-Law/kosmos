"""Claude Code sessions on a matter: the AI tab's list, the session page
and its posts.

A session starts with one click: the plus button posts to ``launch``,
which creates the row and redirects to the page in the new browser tab the
form opened. The model is picked on the page (Fable for administrators
only), the title is taken from the first prompt and can be renamed in
place. ``send`` records the prompt; the agent's answer is the runtime's
job (the next record), and until it is connected the page says so.
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.case.services import get_matter_from_url, matter_folder, set_last_tab

from .models import Conversation, Session, SessionMessage
from .runtime import live_state, request_cancel, service_alive


def session_queryset(matter):
    return (
        Session.objects.filter(matter=matter)
        .select_related("user")
        .annotate(
            message_count=Count("messages"),
            last_activity=Coalesce(Max("messages__created_at"), "created_at"),
        )
        .order_by("-last_activity", "-id")
    )


def get_session_list_context(request, matter):
    """The AI tab's context; also the registered tab's data function."""
    return {
        "matter": matter,
        "sessions": list(session_queryset(matter)),
        "archive_count": Conversation.objects.filter(matter=matter).count(),
    }


@login_required
def sessions_index(request, matter_id):
    matter, matters = get_matter_from_url(request, matter_id)
    set_last_tab(request, matter_id, "ai")
    context = {
        "app": "case",
        "subapp": "ai",
        "matters": matters,
        **get_session_list_context(request, matter),
    }
    return render(request, "ai/sessions/main.html", context)


@login_required
def sessions_list(request, matter_id):
    matter, _ = get_matter_from_url(request, matter_id)
    return render(
        request, "ai/sessions/list.html", get_session_list_context(request, matter)
    )


def _session_for(request, session_id):
    """The session, 404 unless its matter is one the user may open (the
    matter lookup registered for ``session_id`` checks that first)."""
    return get_object_or_404(
        Session.objects.select_related("matter", "user"), pk=session_id
    )


def _page_context(request, session):
    folder = matter_folder(session.matter)
    messages = list(session.messages.select_related("user"))
    open_turn = next((m for m in reversed(messages) if m.is_open), None)
    totals = session.messages.aggregate(
        cost=Sum("cost_usd"),
        input=Sum("input_tokens"),
        cached=Sum("cache_read_tokens"),
        output=Sum("output_tokens"),
    )
    return {
        "session": session,
        "matter": session.matter,
        "folder": folder,
        "messages": messages,
        "open_turn": open_turn,
        "live": live_state(open_turn.id) if open_turn else None,
        "service_alive": service_alive(),
        "totals": totals if totals["cost"] or totals["input"] else None,
        "model_choices": Session.model_choices_for(request.user),
    }


@login_required
@require_POST
def session_launch(request, matter_id):
    """Start a session and open its page (the form targets a new tab)."""
    matter, _ = get_matter_from_url(request, matter_id)
    folder = matter_folder(matter)
    last = (
        Session.objects.filter(matter__in=[matter], user=request.user)
        .order_by("-created_at")
        .first()
    )
    model = last.model if last else Session.DEFAULT_MODEL
    if not Session.user_may_pick(request.user, model):
        model = Session.DEFAULT_MODEL
    session = Session.objects.create(
        matter=matter,
        user=request.user,
        model=model,
        folder=folder.path if folder else "",
    )
    return redirect("ai:session-page", session_id=session.id)


@login_required
def session_page(request, session_id):
    session = _session_for(request, session_id)
    return render(request, "ai/sessions/page.html", _page_context(request, session))


@login_required
def session_messages(request, session_id):
    session = _session_for(request, session_id)
    return render(request, "ai/sessions/messages.html", _page_context(request, session))


@login_required
@require_POST
def session_send(request, session_id):
    """Record the prompt. The first one names the session."""
    session = _session_for(request, session_id)
    text = request.POST.get("message", "").strip()
    if not text:
        return HttpResponseBadRequest("Nothing to send.")
    if session.messages.filter(
        role="assistant", status__in=("pending", "running")
    ).exists():
        return HttpResponse("The agent is still answering the last prompt.", status=409)
    SessionMessage.objects.create(
        session=session, role="user", content=text, user=request.user
    )
    # The answer's row, for the service to fill.
    SessionMessage.objects.create(
        session=session,
        role="assistant",
        content="",
        user=request.user,
        status="pending",
    )
    response_parts = []
    if not session.title:
        session.title = Session.title_from(text)
        session.save(update_fields=["title", "updated_at"])
        response_parts.append(
            render_to_string(
                "ai/sessions/title.html",
                {"session": session, "oob": True},
                request=request,
            )
        )
    response_parts.insert(
        0,
        render_to_string(
            "ai/sessions/messages.html", _page_context(request, session), request
        ),
    )
    response = HttpResponse("".join(response_parts))
    response["HX-Trigger"] = "sessionsChanged"
    return response


@login_required
@require_POST
def session_model(request, session_id):
    """Set the model for the next turn; a model the user may not pick is
    refused."""
    session = _session_for(request, session_id)
    model = request.POST.get("model", "")
    if not Session.user_may_pick(request.user, model):
        return HttpResponse("That model is not available to you.", status=403)
    session.model = model
    session.save(update_fields=["model", "updated_at"])
    response = render(
        request,
        "ai/sessions/model.html",
        {"session": session, "model_choices": Session.model_choices_for(request.user)},
    )
    response["HX-Trigger"] = "sessionsChanged"
    return response


@login_required
@require_POST
def session_rename(request, session_id):
    session = _session_for(request, session_id)
    title = request.POST.get("title", "").strip()
    if title:
        session.title = title[0].upper() + title[1:]
        session.save(update_fields=["title", "updated_at"])
    return render(request, "ai/sessions/title.html", {"session": session})


@login_required
@require_POST
def session_delete(request, session_id):
    session = _session_for(request, session_id)
    session.delete()
    response = HttpResponse(status=204)
    response["HX-Trigger"] = "sessionsChanged"
    return response


@login_required
def session_live(request, session_id):
    """The transcript while a turn runs: polled by the page every two
    seconds until no turn is open."""
    session = _session_for(request, session_id)
    return render(request, "ai/sessions/messages.html", _page_context(request, session))


@login_required
@require_POST
def session_cancel(request, session_id):
    session = _session_for(request, session_id)
    open_turn = (
        session.messages.filter(role="assistant", status__in=("pending", "running"))
        .order_by("-id")
        .first()
    )
    if open_turn is None:
        return HttpResponse(status=204)
    if open_turn.status == "pending":
        # Not picked up yet: nothing to interrupt.
        open_turn.status = "cancelled"
        open_turn.save(update_fields=["status", "updated_at"])
    else:
        request_cancel(open_turn.id)
    return HttpResponse(status=204)
