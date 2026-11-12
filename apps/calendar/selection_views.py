"""Multi-select on the event lists, the firm Calendar's and a matter's
Events tab, and the bulk actions on what is selected.

The selection is a list of ids in the session (apps.management.selection),
one for the firm's list and one for each matter's tab. With a matter, a
route acts on that matter's tab: its selection, its list, its events.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.access import matter_access_required
from apps.calendar import invitations
from apps.calendar.access import event_for_user, events_for_user
from apps.calendar.bulk_forms import BulkAssignForm, BulkMoveForm
from apps.calendar.events import (
    EVENT_STATUSES,
    get_table_data,
    selected_events_key,
)
from apps.calendar.models import Event
from apps.management.selection import (
    clear_selected_ids,
    get_selected_ids,
    select_all_ids,
    selection_response,
    toggle_id,
)
from apps.matters.events.get_event_data import get_event_data
from apps.matters.models import Matter


def _trigger(matter_id):
    return "matterEventChanged" if matter_id else "eventsChanged"


def _selected_events(request, matter_id):
    """The selected events the user may act on. The session's ids are
    filtered again here, so one that is not the user's to see, or not on
    this matter's tab, is left alone."""
    ids = get_selected_ids(request, selected_events_key(matter_id))
    events = events_for_user(Event.objects.filter(id__in=ids), request.user)
    if matter_id:
        events = events.filter(matter_id=matter_id)
    return events


@login_required
@require_POST
@matter_access_required
def events_toggle_select(request, event_id, matter_id=None):
    event = event_for_user(event_id, request.user)
    if matter_id and event.matter_id != matter_id:
        raise Http404("The event is not on this matter")
    toggle_id(request, selected_events_key(matter_id), event_id)

    return selection_response(_trigger(matter_id))


@login_required
@require_POST
@matter_access_required
def events_select_all(request, matter_id=None):
    """Select the events the list shows (the firm list's current page, or
    all of a matter's tab), or clear the selection when they all are."""
    if matter_id:
        matter = get_object_or_404(Matter, pk=matter_id)
        visible = get_event_data(request, matter)["events"]
    else:
        visible = get_table_data(request)["objects"]
    select_all_ids(
        request, selected_events_key(matter_id), [event.id for event in visible]
    )

    return selection_response(_trigger(matter_id))


@login_required
@require_POST
@matter_access_required
def events_clear_selection(request, matter_id=None):
    clear_selected_ids(request, selected_events_key(matter_id))

    return selection_response(_trigger(matter_id))


@login_required
@require_POST
@matter_access_required
def events_bulk_set_status(request, matter_id=None):
    """Set the status of the selected events."""
    status = request.POST.get("status")
    if status not in EVENT_STATUSES:
        return HttpResponse(status=400, content="Unknown status.")
    events = _selected_events(request, matter_id)
    if not events:
        return HttpResponse(status=400, content="No events selected.")

    # Saved one at a time, so each change is in the event's history
    for event in events.exclude(status=status):
        event.status = status
        event.save(update_fields=["status"])
    clear_selected_ids(request, selected_events_key(matter_id))

    return selection_response(_trigger(matter_id))


def _bulk_url(name, matter_id):
    if matter_id:
        return reverse(f"calendar:{name}-matter", args=[matter_id])
    return reverse(f"calendar:{name}")


def _done(request, matter_id):
    clear_selected_ids(request, selected_events_key(matter_id))
    return selection_response(_trigger(matter_id))


def _dialog(request, matter_id, form, **context):
    return render(
        request,
        "calendar/bulk-modal.html",
        {"form": form, "matter_id": matter_id} | context,
    )


@login_required
@matter_access_required
def events_bulk_move(request, matter_id=None):
    """Move the selected events by a number of days, each keeping its
    length: the dialog, and its Apply. Guests are sent the new date."""
    events = _selected_events(request, matter_id)
    if not events:
        return HttpResponse(status=400, content="No events selected.")

    posted = request.method == "POST"
    form = BulkMoveForm(request.POST if posted else None)
    if posted and form.is_valid():
        by = timedelta(days=form.cleaned_data["days"])
        for event in events.exclude(date=None):
            # what the guests were told, to send again now it changes
            before = invitations.details(event)
            event.date += by
            if event.end_date:
                event.end_date += by
            event.save(update_fields=["date", "end_date"])
            invitations.after_change(event, before, request.user)
        return _done(request, matter_id)

    return _dialog(
        request,
        matter_id,
        form,
        title="Move Events",
        action=_bulk_url("bulk-move", matter_id),
        count=events.count(),
        intro="Enter calendar days; a negative number moves them earlier.",
        invited=invitations.with_guests_to_tell(events).count(),
        invited_note="whose guests will be sent the new date",
    )


@login_required
@matter_access_required
def events_bulk_assign(request, matter_id=None):
    """Assign the selected events to the people ticked, in place of whoever
    each was assigned to; nobody ticked makes them the firm's."""
    events = _selected_events(request, matter_id)
    if not events:
        return HttpResponse(status=400, content="No events selected.")

    posted = request.method == "POST"
    form = BulkAssignForm(request.POST if posted else None)
    if posted and form.is_valid():
        assignees = list(form.cleaned_data["assignees"])
        for event in events:
            event.assignees.set(assignees)
        return _done(request, matter_id)

    return _dialog(
        request,
        matter_id,
        form,
        title="Assign Events",
        action=_bulk_url("bulk-assign", matter_id),
        count=events.count(),
        intro="This replaces whoever each event is assigned to now.",
    )


@login_required
@require_POST
@matter_access_required
def events_bulk_delete(request, matter_id=None):
    """Delete the selected events."""
    events = _selected_events(request, matter_id)
    if not events:
        return HttpResponse(status=400, content="No events selected.")

    for event in events:
        # The guests hear it is off before it is deleted
        invitations.send_cancellation(event, list(event.guests.all()), request.user)
        event.delete()

    return _done(request, matter_id)
