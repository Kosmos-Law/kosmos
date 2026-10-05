import logging
import threading

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.views.decorators.http import require_POST

import apps.mail.google as mail_google
from apps.case.ai.status import status_cache
from apps.case.views import get_matter_from_url, get_session_key, set_last_tab
from apps.matters.models import Matter

from .filters import EmailFilter
from .models import Email, GmailAccount

logger = logging.getLogger(__name__)


def get_emails_data(request, matter, matter_id):
    """Synced emails with session-persisted filters applied, newest first."""
    filter_session_key = get_session_key("emails_filter", matter_id)
    filter_data = request.session.get(filter_session_key, {})

    # dedup: the same message synced from two mailboxes shows once
    # (first-synced row wins; provenance rows stay in the DB).
    # Bodies are deferred: the list renders sender/subject/date only, and a
    # big matter's full bodies are megabytes per load (the preview pane
    # fetches each email on click).
    queryset = (
        Email.objects.filter(matter=matter)
        .dedup()
        .defer("body_text", "body_html")
        .order_by("-date")
        .select_related("account")
        .prefetch_related("attachment_files")
    )
    if filter_data:
        emails = EmailFilter(filter_data, queryset=queryset).qs
    else:
        emails = queryset

    current_order = filter_data.get("order_by", "-date")
    if isinstance(current_order, list):
        current_order = current_order[0] if current_order else "-date"

    keyword = filter_data.get("keyword", "")
    if isinstance(keyword, list):
        keyword = keyword[0] if keyword else ""

    # DB-only check (no Gmail round-trip): the scheduled sync refreshes each
    # account's missing_labels every tick, so "your mailbox has no label for
    # this matter" is at most a couple of minutes stale.
    own_account = GmailAccount.objects.filter(user=request.user).first()
    own_missing_label = bool(
        own_account
        and matter.gmail_label_name
        and matter.gmail_label_name in (own_account.missing_labels or [])
    )

    return {
        "emails": emails,
        "email_count": emails.count(),
        "current_order": current_order,
        "keyword": keyword,
        # Only the filter's own fields count: a stray key in the stored
        # dict is not a filter.
        "filters_active": any(
            filter_data.get(name)
            for name in EmailFilter.base_filters
            if name != "order_by"
        ),
        "gmail_linked": mail_google.check_credentials(),
        "own_missing_label": own_missing_label,
    }


@login_required
def emails_index(request, matter_id):
    """Main emails view (the case Emails tab)."""
    matter, matters = get_matter_from_url(request, matter_id)
    set_last_tab(request, matter_id, "emails")

    context = {
        "app": "matters",
        "subapp": "emails",
        "matter": matter,
        "matters": matters,
    } | get_emails_data(request, matter, matter_id)

    return render(request, "case/emails/main.html", context)


@login_required
def emails_list(request, matter_id):
    """List partial for HTMX refreshes."""
    matter, matters = get_matter_from_url(request, matter_id)

    context = {
        "matter": matter,
        "matters": matters,
    } | get_emails_data(request, matter, matter_id)

    return render(request, "case/emails/list.html", context)


@login_required
def emails_filter(request, matter_id):
    """Filter modal for emails (mirrors the notes filter modal)."""
    matter, matters = get_matter_from_url(request, matter_id)
    filter_session_key = get_session_key("emails_filter", matter_id)

    if request.method == "POST":
        if request.POST.get("reset"):
            # Clear Filters: store no filter, not the button's own value.
            filter_data = {}
        else:
            filter_data = {
                key: value
                for key, value in request.POST.items()
                if key != "csrfmiddlewaretoken"
            }
        request.session[filter_session_key] = filter_data
        request.session.modified = True
        return HttpResponse(status=204, headers={"HX-Trigger": "emailsChanged"})

    filter_data = request.session.get(filter_session_key, {})
    filter_obj = EmailFilter(filter_data, queryset=Email.objects.filter(matter=matter))

    return render(
        request, "case/emails/filter.html", {"filter": filter_obj, "matter": matter}
    )


@login_required
def emails_filter_keyword(request, matter_id):
    """Filter emails by subject keyword (toolbar live search)."""
    matter, _ = get_matter_from_url(request, matter_id)
    filter_session_key = get_session_key("emails_filter", matter_id)
    filter_data = request.session.get(filter_session_key, {})
    keyword = request.GET.get("keyword", "").strip()

    if keyword:
        filter_data["keyword"] = keyword
    else:
        filter_data.pop("keyword", None)

    request.session[filter_session_key] = filter_data

    context = {"matter": matter} | get_emails_data(request, matter, matter_id)
    return render(request, "case/emails/table.html", context)


@login_required
def emails_sort(request, matter_id, order):
    """Sort emails by field, toggling direction on repeat clicks."""
    filter_session_key = get_session_key("emails_filter", matter_id)
    filter_data = request.session.get(filter_session_key, {})

    current_order = filter_data.get("order_by", "")
    if isinstance(current_order, list):
        current_order = current_order[0] if current_order else ""
    if current_order == order:
        new_order = f"-{order}" if not current_order.startswith("-") else order
    else:
        new_order = order

    filter_data["order_by"] = new_order
    request.session[filter_session_key] = filter_data
    request.session.modified = True

    return redirect("case:emails-list", matter_id=matter_id)


@login_required
def emails_list_items(request, matter_id):
    """The list column alone, for a refresh that keeps the open email.

    Promoting an email or changing its importance changes its row; reloading
    the whole tab would close the reading pane the user is looking at.
    """
    matter, _ = get_matter_from_url(request, matter_id)
    context = {"matter": matter} | get_emails_data(request, matter, matter_id)
    return render(request, "case/emails/list-items.html", context)


def _own_gmail_url(email, user):
    """A Gmail link into the user's own mailbox for this message, or None.

    A message id is local to one mailbox, so the link only opens for the
    person that mailbox belongs to. The row shown may be a colleague's copy
    (the list collapses duplicates to the first-synced one): prefer the
    user's own copy of the same message when there is one.
    """
    if email.account_id is None:
        # Rows from before per-user mailboxes belong to the first mailbox.
        first = GmailAccount.objects.order_by("id").first()
        return email.gmail_url if first and first.user_id == user.id else None
    if email.account.user_id == user.id:
        return email.gmail_url
    if not email.message_id:
        return None
    own = (
        Email.objects.filter(
            matter_id=email.matter_id,
            message_id=email.message_id,
            account__user=user,
        )
        .select_related("account")
        .first()
    )
    return own.gmail_url if own else None


def _preview_response(request, email, changed=False):
    """The reading pane for one email. ``changed`` also refreshes the list
    column, whose row shows the importance and the promoted mark."""
    response = render(
        request,
        "case/emails/preview.html",
        {"email": email, "gmail_url": _own_gmail_url(email, request.user)},
    )
    if changed:
        response["HX-Trigger"] = "emailItemsChanged"
    return response


@login_required
def email_preview(request, email_id):
    """Preview-pane partial for one email."""
    email = get_object_or_404(Email, pk=email_id)
    return _preview_response(request, email)


@login_required
@require_POST
def email_promote(request, email_id):
    """Promote an email to a Correspondence Document (PDF in the record)."""
    from .promote import promote_email

    email = get_object_or_404(Email, pk=email_id)
    base_url = request.build_absolute_uri("/").rstrip("/")
    try:
        promote_email(email, request.user, base_url)
    except Exception:
        return HttpResponse(
            '<p class="error-text">Failed to render the email to PDF. '
            "Try again, or check the logs.</p>"
        )
    email.refresh_from_db()
    return _preview_response(request, email, changed=True)


@login_required
@require_POST
def email_importance(request, email_id, value):
    """Set an email's importance and re-render its preview pane."""
    email = get_object_or_404(Email, pk=email_id)
    if 1 <= value <= 7:
        email.importance = value
        email.save(update_fields=["importance"])
    return _preview_response(request, email, changed=True)


# ---------------------------------------------------------------------------
# Gmail label linking (mirrors the Notes tab's Drive folder linking)
# ---------------------------------------------------------------------------


@login_required
def label_link_modal(request, matter_id):
    """Modal to pick this matter's Gmail label from a live list.

    Labels are read from the requester's own mailbox only: a user who has
    not connected one is shown no list (never a colleague's labels) and can
    still create the label named after the matter. What gets stored is the
    label NAME — the cross-mailbox contract every account resolves for
    itself.
    """
    matter, _ = get_matter_from_url(request, matter_id)

    own_account = mail_google.account_for(request.user)
    labels = mail_google.list_matter_labels(own_account)
    # Labels already linked to a different matter (prevent mis-linking).
    taken = {
        m.gmail_label_name: m
        for m in Matter.objects.exclude(pk=matter.pk)
        .exclude(gmail_label_name__isnull=True)
        .exclude(gmail_label_name="")
    }
    label_rows = [
        {
            **label,
            "taken": label["name"] in taken,
            "taken_by": _matter_name_for(request.user, taken.get(label["name"])),
        }
        for label in labels
    ]

    # "Create a label named after the matter" shortcut: the sync provisions
    # the label in every mailbox, so nobody has to touch Gmail first. Only
    # offered while the name is unused and unlinked.
    suggested = mail_google.default_label_name(matter)
    if suggested in taken or any(label["name"] == suggested for label in labels):
        suggested = None
    prefix = f"{settings.GMAIL_LABEL_ROOT}/" if settings.GMAIL_LABEL_ROOT else ""
    suggested_short = suggested.removeprefix(prefix) if suggested else None

    context = {
        "matter": matter,
        "labels": label_rows,
        "current": matter.gmail_label_name,
        "linked": mail_google.check_credentials(),
        "own_mailbox": own_account is not None,
        "label_root": settings.GMAIL_LABEL_ROOT,
        "suggested_label": suggested,
        "suggested_short": suggested_short,
    }
    return render(request, "case/emails/label-link-modal.html", context)


def _matter_name_for(user, matter):
    """The matter's name when the user may see that matter, else None.

    Another matter holding a label is worth saying; which matter it is, is
    not something to tell a user who is not on it.
    """
    if matter is not None and user.has_matter_access(matter):
        return str(matter)
    return None


def _queue_resync(matter):
    """Resync via django-q so linking a large label doesn't block the request."""
    try:
        from django_q.tasks import async_task

        async_task("apps.mail.google.resync_matter_by_id", matter.id)
    except Exception:
        mail_google.resync_matter(matter)


def _refresh_cache_key(matter_id):
    return f"emails_refresh_{matter_id}"


def _start_refresh(matter):
    """Run the per-matter resync on a daemon thread.

    Deliberately NOT the django-q queue: an on-demand refresh must not sit
    behind whatever the shared queue is chewing on (a wedged attachment
    batch once stranded the button in its syncing state for the queue's
    whole retry cycle). Completion is signalled through the cross-process
    ai_status cache, the same store the AI status indicator uses: prod runs
    several gunicorn workers and a poll usually lands in one other than the
    one running the thread, so a per-process flag read as "finished" from
    the first poll and the button flipped back while the sync ran."""
    key = _refresh_cache_key(matter.id)

    def run():
        try:
            mail_google.resync_matter(matter)
        except Exception:
            logger.exception("On-demand email resync failed for matter %s", matter.id)
        finally:
            status_cache.delete(key)

    threading.Thread(target=run, daemon=True).start()


@login_required
@require_POST
def emails_refresh(request, matter_id):
    """On-demand resync of this matter, ahead of the scheduled sync.

    Swaps the Refresh button for a pill that polls emails_refresh_status
    until the resync thread clears the running flag. A second click while
    one is running just re-attaches to the run in flight."""
    matter, _ = get_matter_from_url(request, matter_id)
    if not (matter.gmail_label_name and mail_google.check_credentials()):
        return HttpResponse(status=204, headers={"HX-Trigger": "emailsChanged"})
    key = _refresh_cache_key(matter.id)
    if status_cache.get(key) != "running":
        status_cache.set(key, "running", 600)
        _start_refresh(matter)
    return render(
        request,
        "case/emails/refresh-button.html",
        {"matter": matter, "syncing": True, "polls": 0},
    )


@login_required
def emails_refresh_status(request, matter_id):
    """Poll target for the refresh pill: swap back + reload once the
    resync thread finishes. The poll cap (150 × 2s, matching the running
    flag's 600s timeout) backstops a thread that died without cleanup."""
    matter, _ = get_matter_from_url(request, matter_id)
    try:
        polls = int(request.GET.get("polls", 0))
    except ValueError:
        polls = 0

    if status_cache.get(_refresh_cache_key(matter.id)) == "running" and polls < 150:
        return render(
            request,
            "case/emails/refresh-button.html",
            {"matter": matter, "syncing": True, "polls": polls + 1},
        )

    response = render(request, "case/emails/refresh-button.html", {"matter": matter})
    response["HX-Trigger"] = "emailsChanged"
    return response


@login_required
@require_POST
def label_link(request, matter_id):
    """Set this matter's Gmail label and resync its emails."""
    matter, _ = get_matter_from_url(request, matter_id)
    # create_label_name is the "create a label named after the matter"
    # shortcut; the sync provisions it in every mailbox on resync.
    label_name = (
        request.POST.get("create_label_name") or request.POST.get("label_name") or ""
    ).strip()

    # 200 on a refusal so HTMX swaps the message into the modal's error slot.
    if not label_name:
        # Nothing chosen is not a request to unlink: saving an empty label
        # here used to queue a resync that emptied the matter. Unlink is its
        # own, confirmed action.
        return HttpResponse('<p class="error-text">Choose a label to link first.</p>')

    clash = (
        Matter.objects.exclude(pk=matter.pk).filter(gmail_label_name=label_name).first()
    )
    if clash:
        clash_name = _matter_name_for(request.user, clash) or "another matter"
        return HttpResponse(
            format_html(
                '<p class="error-text">“{}” is already linked to {}. '
                "Unlink it there first.</p>",
                label_name,
                clash_name,
            )
        )

    matter.gmail_label_name = label_name
    matter.save(update_fields=["gmail_label_name"])
    _queue_resync(matter)

    return HttpResponse(status=204, headers={"HX-Refresh": "true"})


@login_required
@require_POST
def label_unlink(request, matter_id):
    """Unlink this matter's Gmail label and remove its synced emails."""
    matter, _ = get_matter_from_url(request, matter_id)
    matter.gmail_label_name = None
    matter.save(update_fields=["gmail_label_name"])
    # The user confirmed removing the emails; a resync no longer does that
    # for a matter with no label (a closed matter keeps its emails).
    mail_google.remove_matter_emails(matter)

    return HttpResponse(status=204, headers={"HX-Refresh": "true"})
