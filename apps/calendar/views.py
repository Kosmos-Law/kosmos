import json
from datetime import datetime, timedelta

from dateutil import parser
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

import apps.calendar.google as google
import apps.calendar.sync as sync
from apps.accounts.access import matter_access_required
from apps.calendar.access import event_for_user, matters_for_events
from apps.calendar.filter import EventFilter
from apps.calendar.forms import EventForm
from apps.calendar.models import Event
from apps.management.filter_manager import FilterManager
from utils.toasts import toast_warning

from .events import (
    SESSION_KEY,
    default_end_time,
    event_filter,
    get_table_data,
    saved_filter,
    toolbar_context,
)

# Shown when Google Calendar is connected but a sync push fails (e.g. an
# expired/revoked token). The local save still succeeds — see
# google.best_effort — so this is a non-blocking warning, not an error.
GOOGLE_SYNC_FAILED_MSG = (
    "Event saved, but couldn't sync to Google Calendar. Reconnect it in Settings."
)


def _event_change_response(
    trigger, sync_failed=False, sync_message=GOOGLE_SYNC_FAILED_MSG
):
    """A 204 + HX-Trigger response for an event change, plus a warning toast
    when the (best-effort) Google sync reported failure."""
    response = HttpResponse(status=204, headers={"HX-Trigger": trigger})
    if sync_failed:
        toast_warning(response, sync_message)
    return response


@login_required
def events_index(request):
    today = timezone.localdate()
    third_day = today + timedelta(days=3)

    view_mode = request.session.get("events_view_mode", "calendar")

    context = {
        "app": "events",
        "third_day": third_day,
        "view_mode": view_mode,
    } | get_table_data(request)

    return render(request, "calendar/main.html", context)


@login_required
def events_list(request):
    """Returns the appropriate view (list or calendar) based on session."""
    today = timezone.localdate()
    third_day = today + timedelta(days=3)

    view_mode = request.session.get("events_view_mode", "calendar")

    context = {
        "app": "events",
        "third_day": third_day,
        "view_mode": view_mode,
    }

    if view_mode == "calendar":
        context = context | toolbar_context(request)
        return render(request, "calendar/calendar.html", context)

    context = context | get_table_data(request)
    return render(request, "calendar/list.html", context)


@login_required
def events_filter(request):
    filter_manager = FilterManager(request, EventFilter, SESSION_KEY)

    if filter_manager.process_filter():
        return HttpResponse(status=204, headers={"HX-Trigger": "eventsChanged"})

    return render(request, "calendar/filter.html", {"filter": event_filter(request)})


@login_required
def events_filter_menus(request):
    """The toolbar's status, assignee and matter menus as the saved filter
    now stands. The calendar view asks for these after a filter change,
    because it refetches its events without re-rendering the toolbar."""
    return render(request, "calendar/filter-menus.html", toolbar_context(request))


@login_required
def events_filter_quick(request, quick_filter):
    filter_manager = FilterManager(request, EventFilter, SESSION_KEY)
    filter_manager.apply_quick_filter(quick_filter)

    return HttpResponse(status=204, headers={"HX-Trigger": "eventsChanged"})


def _save_filter_value(request, key, value):
    """Set one value of the saved filter, keeping the rest."""
    events_filter = saved_filter(request)
    events_filter[key] = value if value else ""
    request.session[SESSION_KEY] = events_filter
    request.session.modified = True


@login_required
def events_filter_status(request, status):
    _save_filter_value(request, "status", status)

    response = render(
        request,
        "calendar/status-dropdown.html",
        {"events_filter_status": status},
    )
    response["HX-Trigger"] = "eventsChanged"
    return response


@login_required
def events_filter_assigned(request, assigned):
    """Filter events by assigned_to value."""
    _save_filter_value(request, "assigned_to", assigned)

    response = render(
        request, "calendar/assigned-dropdown.html", toolbar_context(request)
    )
    response["HX-Trigger"] = "eventsChanged"
    return response


@login_required
def events_filter_matter(request, matter):
    """Filter events by matter value."""
    _save_filter_value(request, "matter", matter)

    # The menu is rebuilt from this user's own choices, so naming a matter
    # that is not theirs neither filters by it nor shows its name.
    response = render(
        request, "calendar/matter-dropdown.html", toolbar_context(request)
    )
    response["HX-Trigger"] = "eventsChanged"
    return response


@login_required
def events_filter_sort(request, order):
    filter_data = saved_filter(request)

    current_order = filter_data.get("order_by", "")
    if isinstance(current_order, list):
        current_order = current_order[0] if current_order else ""

    if current_order == order:
        new_order = f"-{order}" if not current_order.startswith("-") else order
    else:
        new_order = order

    filter_data["order_by"] = new_order
    request.session[SESSION_KEY] = filter_data
    request.session.modified = True

    return HttpResponse(status=204, headers={"HX-Trigger": "eventsChanged"})


def _initial_from_click(request):
    """The date, and the start time when a time slot was clicked, that the
    calendar asks Add Event to open with. Anything unreadable falls back to
    today with no time."""
    initial = {"date": timezone.localdate()}

    # Only the date part is read, so a full date-time here still lands on
    # the day that was clicked.
    try:
        initial["date"] = datetime.strptime(
            request.GET.get("date", "")[:10], "%Y-%m-%d"
        ).date()
    except ValueError:
        pass

    try:
        initial["start_time"] = datetime.strptime(
            request.GET.get("start_time", "")[:5], "%H:%M"
        ).time()
    except ValueError:
        pass

    return initial


@login_required
@matter_access_required
def events_add(request, matter_id=None, origin="events"):
    # identify the origin of the request (events or agenda)
    if request.method == "GET":
        request.session["origin"] = origin
        request.session.modified = True

    # set the origin of the request, defaulting to "events"
    origin = request.session.get("origin", "events")

    # The matter the form was opened from stays in the list whatever its
    # status. Left out, a Complete or Closed matter was missing from the
    # select and the event saved with no matter.
    matters = matters_for_events(request.user, include_id=matter_id)

    # if applicable, process any post data submitted by user
    if request.method == "POST":
        form = EventForm(request.POST, matters=matters, use_required_attribute=False)
        if form.is_valid():
            # initialize event data
            event = form.save(commit=False)
            event.user = request.user

            # An event saved with a start and no end runs for an hour
            if event.start_time and not event.end_time:
                event.end_time = default_end_time(event.start_time)

            event.save()

            # Mirror to Google (Pending events only); records google_synced_at,
            # or leaves it for reconcile() to retry if the push fails.
            sync_failed = sync.push_event(event) == "failed"

            trigger = "matterEventChanged" if origin == "matters" else "eventsChanged"
            return _event_change_response(trigger, sync_failed)

    # if no post data has been submitted, show the contact form
    else:
        initial = _initial_from_click(request)
        if matter_id:
            initial["matter"] = matter_id
        form = EventForm(initial=initial, matters=matters, use_required_attribute=False)

    # When no matter is pre-selected, autofocus the matter select instead of description
    if not matter_id:
        form.fields["description"].widget.attrs.pop("autofocus", None)
        form.fields["matter"].widget.attrs["autofocus"] = "autofocus"

    google_connected = google.check_credentials()

    today = timezone.localdate().strftime("%Y-%m-%d")

    # The form posts back to the address that names its matter, so the same
    # matter list validates the submission.
    if matter_id:
        action = reverse("calendar:add-matter-origin", args=[matter_id, origin])
    else:
        action = reverse("calendar:add")

    context = {
        "app": "events",
        "today": today,
        "edit": False,
        "add": True,
        "results": None,
        "action": action,
        "google_connected": google_connected,
        "form": form,
    }

    return render(request, "calendar/form.html", context)


@login_required
def events_edit(request, id, origin="events"):
    # identify the origin of the request (events or agenda)
    if request.method == "GET":
        request.session["origin"] = origin
    origin = request.session.get("origin", "events")

    event = event_for_user(id, request.user)

    # The matter the event is already on stays in the list even when it is
    # closed, so the select can show it.
    matters = matters_for_events(request.user, include_id=event.matter_id)

    if request.method == "POST":
        form = EventForm(
            request.POST,
            instance=event,
            matters=matters,
            use_required_attribute=False,
        )

        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user

            # An event saved with a start and no end runs for an hour
            if event.start_time and not event.end_time:
                event.end_time = default_end_time(event.start_time)

            event.save()

            sync_failed = sync.push_event(event) == "failed"

            trigger = "matterEventChanged" if origin == "matters" else "eventsChanged"
            return _event_change_response(trigger, sync_failed)

    else:
        form = EventForm(
            instance=event,
            initial={"matter": event.matter},
            matters=matters,
            use_required_attribute=False,
        )

    google_connected = google.check_credentials()

    context = {
        "app": "events",
        "edit": True,
        "add": False,
        "results": None,
        "action": f"/events/{id}/edit",
        "event": event,
        "google_connected": google_connected,
        "form": form,
        "origin": origin,
    }

    return render(request, "calendar/form.html", context)


@login_required
@require_http_methods(["POST", "DELETE"])
def events_delete(request, id, origin="events"):
    # The origin that counts is the one saved when the Edit Event dialog was
    # opened: its Delete button names "events" wherever it was opened from.
    origin = request.session.get("origin", "events")

    event = event_for_user(id, request.user)

    # Remove from Google (queues a retry on failure) before deleting locally.
    sync_failed = sync.delete_event_remote(event) == "failed"

    event.delete()

    trigger = "matterEventChanged" if origin == "matters" else "eventsChanged"
    return _event_change_response(
        trigger,
        sync_failed,
        "Event deleted, but couldn't remove it from Google Calendar.",
    )


def _deadline_inputs(request):
    """The calculator's start date and day count, or the message to show
    when either cannot be read."""
    try:
        initial_date = parser.parse(request.POST.get("initial_date", ""))
    except (ValueError, OverflowError):
        return None, None, "Enter a start date."

    try:
        days = int(request.POST.get("days", "").strip())
    except ValueError:
        return None, None, "Days must be a whole number."

    return initial_date, days, None


@login_required
def events_deadline_results(request, matter_id=None):
    initial_date, days, error = _deadline_inputs(request)

    # calculate deadline; a count that runs past the calendar's last year
    # is refused like any other unusable entry
    deadline = None
    if not error:
        try:
            deadline = initial_date + timedelta(days=days)
        except OverflowError:
            error = "That many days is out of range."

    if error:
        return render(
            request, "calendar/deadline-calculator-results.html", {"error": error}
        )

    # determine whether deadline falls on a weekday
    # if so, provide the date of the next Monday
    deadline_weekday = deadline.strftime("%A")
    next_workday = None
    if deadline_weekday == "Saturday":
        next_workday = deadline + timedelta(days=2)
    if deadline_weekday == "Sunday":
        next_workday = deadline + timedelta(days=1)

    # store the ddeadline results in the calc dictionary
    results = {}
    results["initial_date"] = initial_date
    results["days"] = days
    results["deadline"] = deadline
    results["deadline_weekday"] = deadline_weekday
    results["next_workday"] = next_workday

    context = {
        "results": results,
    }

    return render(request, "calendar/deadline-calculator-results.html", context)


@login_required
def events_deadline_form(request):
    today = timezone.localdate()
    today = today.strftime("%Y-%m-%d")
    context = {
        "today": today,
    }
    return render(request, "calendar/deadline-calculator-form.html", context)


@login_required
def events_deadline_modal(request):
    today = timezone.localdate().strftime("%Y-%m-%d")
    context = {"today": today}
    return render(request, "calendar/deadline-calculator-modal.html", context)


@login_required
def events_calendar(request):
    """Render the calendar view partial."""
    today = timezone.localdate()
    third_day = today + timedelta(days=3)

    context = {
        "app": "events",
        "third_day": third_day,
        "view_mode": "calendar",
    } | toolbar_context(request)
    return render(request, "calendar/calendar.html", context)


def _feed_date(value):
    """The date in one of the feed's ISO date or date-time parameters."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


@login_required
@matter_access_required
def events_api(request, matter_id=None):
    """
    JSON API for FullCalendar event feed.
    Exception to HTMX HTML-only rule: calendar requires JSON.

    With matter_id (the matter detail Events tab), the feed is scoped to that
    matter and honours the tab's own per-matter status filter instead of the
    global events filter.
    """
    start_param = request.GET.get("start")
    end_param = request.GET.get("end")

    # Parse FullCalendar's ISO date parameters
    try:
        if start_param:
            start_date = _feed_date(start_param)
        else:
            start_date = timezone.localdate() - timedelta(days=30)

        if end_param:
            end_date = _feed_date(end_param)
        else:
            end_date = timezone.localdate() + timedelta(days=60)
    except ValueError:
        return HttpResponseBadRequest("start and end must be ISO dates.")

    if matter_id:
        events = Event.objects.filter(matter_id=matter_id)
        status = request.session.get(f"matter_events_filter_{matter_id}", "Pending")
        if status:
            events = events.filter(status=status)
    else:
        # The saved filter (the default when none is saved), over the events
        # this user may see
        events = event_filter(request).qs
    events = events.filter(date__gte=start_date, date__lte=end_date)

    # Convert to FullCalendar format
    calendar_events = []
    for event in events:
        matter_name = event.matter.name if event.matter else ""
        description = event.description or "Untitled"

        # Build title: {Matter} - {Description} - {User Initials}
        title_parts = []
        if matter_name:
            title_parts.append(matter_name)
        title_parts.append(description)
        if event.assigned_to and event.assigned_to.initials:
            title_parts.append(event.assigned_to.initials)
        title = " - ".join(title_parts)

        fc_event = {
            "id": str(event.id),
            "title": title,
            "extendedProps": {
                "matter": event.matter.name if event.matter else "",
                "matter_id": event.matter.id if event.matter else None,
                "event_type": event.event_type or "",
                "location": event.location or "",
                "party": event.party or "",
                "status": event.status or "",
            },
        }

        # Handle timed vs all-day events
        if event.start_time and event.end_time:
            fc_event["start"] = f"{event.date}T{event.start_time}"
            fc_event["end"] = f"{event.date}T{event.end_time}"
            fc_event["allDay"] = False
        elif event.start_time:
            fc_event["start"] = f"{event.date}T{event.start_time}"
            fc_event["allDay"] = False
        else:
            fc_event["start"] = str(event.date)
            fc_event["allDay"] = True

        # Add status-based styling
        classes = []
        if event.status == "Pending":
            classes.append("fc-event-pending")
        elif event.status == "Complete":
            classes.append("fc-event-complete")
        elif event.status == "Missed":
            classes.append("fc-event-missed")
        if not event.matter:
            classes.append("fc-event-no-matter")
        if classes:
            fc_event["className"] = " ".join(classes)

        calendar_events.append(fc_event)

    return JsonResponse(calendar_events, safe=False)


def _quick_update_changes(body):
    """The date and times a drag or resize asks for, or None when the
    request is not the JSON object of dates and times the calendar sends."""
    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    changes = {}
    try:
        if "date" in data:
            changes["date"] = datetime.strptime(data["date"], "%Y-%m-%d").date()
        for field in ("start_time", "end_time"):
            if field in data:
                changes[field] = (
                    datetime.strptime(data[field], "%H:%M:%S").time()
                    if data[field]
                    else None
                )
    except (ValueError, TypeError):
        return None
    return changes


@login_required
@require_POST
def events_quick_update(request, id):
    """
    Quick update for drag-drop operations.
    Only updates date/time fields.
    """
    event = event_for_user(id, request.user)

    # Everything is read before anything is set, so a request that cannot
    # be read changes nothing.
    changes = _quick_update_changes(request.body)
    if changes is None:
        return HttpResponseBadRequest("Unreadable date or time.")

    for field, value in changes.items():
        setattr(event, field, value)

    event.save()

    # Sync to Google Calendar
    sync_failed = sync.push_event(event) == "failed"

    return _event_change_response("eventsChanged", sync_failed)


@login_required
@require_POST
def events_view_mode(request, mode):
    """Toggle between list and calendar view modes."""
    request.session["events_view_mode"] = mode
    request.session.modified = True
    return HttpResponse(status=204, headers={"HX-Trigger": "eventsViewChanged"})
