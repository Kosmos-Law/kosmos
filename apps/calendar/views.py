import json
from datetime import datetime, timedelta

from dateutil import parser
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.access import matter_access_required
from apps.calendar import holidays, invitations, meetings
from apps.calendar.access import event_for_user, matters_for_events
from apps.calendar.feed import event_entry, feed_date, task_entry
from apps.calendar.filter import EventFilter, assignee_tokens
from apps.calendar.forms import EventForm
from apps.calendar.guest_views import guests_context
from apps.calendar.models import Event
from apps.calendar.reminder_views import reminders_context
from apps.management.filter_manager import FilterManager
from apps.matters.models import Matter
from utils.toasts import toast_warning

from .events import (
    SESSION_KEY,
    SHOW_HOLIDAYS_KEY,
    SHOW_TASKS_KEY,
    default_end_time,
    event_filter,
    get_table_data,
    matter_menu_context,
    saved_filter,
    show_holidays,
    show_tasks,
    toolbar_context,
)


def _event_change_response(trigger):
    """A 204 that tells the page an event changed."""
    return HttpResponse(status=204, headers={"HX-Trigger": trigger})


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
@matter_access_required
def events_overlays(request, matter_id=None):
    """The rows of the calendar's menu (the sliders button on the toolbar)
    as the session now has them, re-rendered after a change so each check
    row posts the state it would move to. With a matter, the rows are a
    matter's Events tab's: the overlays and the tab's own view switch."""
    if matter_id:
        matter = get_object_or_404(Matter, pk=matter_id)
        context = matter_menu_context(request, matter)
    else:
        context = toolbar_context(request)
    return render(request, "calendar/menu-items.html", context)


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
@require_POST
def events_filter_assigned(request, assigned):
    """Tick or untick one assignee in the saved filter (Firm, or a user
    by id); with none named, untick them all. The menus re-render on
    eventsChanged; assigneesToggled has the page reopen this one, so a
    second tick follows the first."""
    events_filter = saved_filter(request)
    ticked = assignee_tokens(events_filter.get("assigned_to"))
    if not assigned:
        ticked = []
    elif assigned in ticked:
        ticked.remove(assigned)
    else:
        ticked.append(assigned)
    events_filter["assigned_to"] = ticked
    request.session[SESSION_KEY] = events_filter
    request.session.modified = True

    return HttpResponse(
        status=204,
        headers={
            "HX-Trigger": json.dumps({"eventsChanged": None, "assigneesToggled": None})
        },
    )


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
            # The assignees are a many-to-many, saved after the row
            form.save_m2m()

            trigger = "matterEventChanged" if origin == "matters" else "eventsChanged"
            return _event_change_response(trigger)

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
        "form": form,
    }

    return render(request, "calendar/form.html", context)


@login_required
def events_detail(request, id, origin="events"):
    """The event as Google Calendar opens one: its details to read, the
    meeting link and any link in its details to follow, and Edit to change
    it. The origin is kept for Edit and Delete, as the edit dialog keeps
    it, so a change made from a matter's tab refreshes that tab."""
    request.session["origin"] = origin
    event = event_for_user(id, request.user)

    context = {
        "event": event,
        "origin": origin,
        "edit_url": reverse("calendar:edit-origin", args=[event.id, origin]),
        "details_html": meetings.details_html(event.details),
        "map_url": meetings.map_url(event.location) if event.location else "",
        "meeting_host": meetings.meeting_host(event.meeting_url),
        "assignees": event.assignee_names,
        "guests": list(event.guests.all()),
        "reminders": list(event.reminders.filter(user=request.user)),
    }
    return render(request, "calendar/detail.html", context)


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

        # what the guests were told, to send again if it changes
        before = invitations.details(event)

        if form.is_valid():
            event = form.save(commit=False)
            event.user = request.user

            # An event saved with a start and no end runs for an hour
            if event.start_time and not event.end_time:
                event.end_time = default_end_time(event.start_time)

            event.save()
            form.save_m2m()
            invitations.after_change(event, before, request.user)

            trigger = "matterEventChanged" if origin == "matters" else "eventsChanged"
            return _event_change_response(trigger)

    else:
        form = EventForm(
            instance=event,
            initial={"matter": event.matter},
            matters=matters,
            use_required_attribute=False,
        )

    context = (
        {
            "app": "events",
            "edit": True,
            "add": False,
            "results": None,
            "action": f"/events/{id}/edit",
            "event": event,
            "detail_url": reverse("calendar:detail-origin", args=[id, origin]),
            "form": form,
            "origin": origin,
        }
        | reminders_context(event, request.user)
        | guests_context(event)
    )

    return render(request, "calendar/form.html", context)


@login_required
@require_http_methods(["POST", "DELETE"])
def events_delete(request, id, origin="events"):
    # The origin that counts is the one saved when the Edit Event dialog was
    # opened: its Delete button names "events" wherever it was opened from.
    origin = request.session.get("origin", "events")

    event = event_for_user(id, request.user)

    # The guests hear it is off before it is deleted
    invitations.send_cancellation(event, list(event.guests.all()), request.user)
    event.delete()

    trigger = "matterEventChanged" if origin == "matters" else "eventsChanged"
    return _event_change_response(trigger)


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

    # A deadline that falls on a weekend or a federal holiday runs to the
    # next court day, as the rules of procedure have it
    deadline_day = deadline.date()
    deadline_weekday = deadline.strftime("%A")
    holiday = holidays.name_of(deadline_day)
    next_workday = None
    if not holidays.is_court_day(deadline_day):
        next_workday = holidays.next_court_day(deadline_day)

    results = {
        "initial_date": initial_date,
        "days": days,
        "deadline": deadline,
        "deadline_weekday": deadline_weekday,
        "holiday": holiday,
        "next_workday": next_workday,
    }

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
            start_date = feed_date(start_param)
        else:
            start_date = timezone.localdate() - timedelta(days=30)

        if end_param:
            end_date = feed_date(end_param)
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
    # An event over several days counts from its first day to its last, so
    # one that began before the range still shows in it
    events = (
        events.filter(date__lte=end_date)
        .filter(Q(end_date__gte=start_date) | Q(end_date=None, date__gte=start_date))
        .select_related("matter")
        .prefetch_related("assignees")
    )

    calendar_events = [event_entry(event) for event in events]

    # The overlays: on a matter's tab, the user's tasks on that matter
    if show_tasks(request):
        calendar_events.extend(
            _task_feed(request.user, start_date, end_date, matter_id=matter_id)
        )
    if show_holidays(request):
        calendar_events.extend(holidays.feed(start_date, end_date))

    return JsonResponse(calendar_events, safe=False)


def _task_feed(user, first, last, matter_id=None):
    """The user's open tasks due in the range (on one matter, when given),
    as FullCalendar events: an all-day entry (a task has a day, not a
    time) told from an event by its id prefix and its kind, which may be
    dragged to another day but not stretched."""
    from apps.tasks.constants import STATUS_COMPLETE
    from apps.tasks.models import Task

    tasks = (
        Task.objects.filter(user=user, date_due__gte=first, date_due__lte=last)
        .exclude(status=STATUS_COMPLETE)
        .select_related("matter")
    )
    if matter_id:
        tasks = tasks.filter(matter_id=matter_id)
    return [task_entry(task) for task in tasks]


@login_required
@require_POST
def events_show_tasks(request, state):
    """Show the user's open tasks on the calendar beside the events, or
    hide them. The grid refetches its events; the toolbar re-renders."""
    if state not in ("on", "off"):
        return HttpResponseBadRequest("Unknown state.")
    request.session[SHOW_TASKS_KEY] = state == "on"
    request.session.modified = True
    return HttpResponse(status=204, headers={"HX-Trigger": "eventsChanged"})


@login_required
@require_POST
def events_show_holidays(request, state):
    """Show US federal holidays on the calendar beside the events, or
    hide them."""
    if state not in ("on", "off"):
        return HttpResponseBadRequest("Unknown state.")
    request.session[SHOW_HOLIDAYS_KEY] = state == "on"
    request.session.modified = True
    return HttpResponse(status=204, headers={"HX-Trigger": "eventsChanged"})


@login_required
@require_POST
def events_task_done(request, task_id):
    """A task's box on the calendar: mark it done. A task whose checklist
    is not finished stays open, and the calendar is told why."""
    from apps.checklists.models import can_complete_task
    from apps.tasks.access import task_for_user
    from apps.tasks.constants import CHECKLIST_INCOMPLETE_MESSAGE, STATUS_COMPLETE

    task = task_for_user(task_id, request.user)
    if task.status != STATUS_COMPLETE:
        if not can_complete_task(task):
            return toast_warning(HttpResponse(status=409), CHECKLIST_INCOMPLETE_MESSAGE)
        task.status = STATUS_COMPLETE
        task.save()
    return HttpResponse(status=204, headers={"HX-Trigger": "tasksListChanged"})


@login_required
@require_POST
def events_task_date(request, task_id):
    """A task dragged to another day on the calendar keeps only its new
    due date."""
    from apps.tasks.access import task_for_user

    task = task_for_user(task_id, request.user)
    try:
        task.date_due = datetime.strptime(
            request.POST.get("date_due", ""), "%Y-%m-%d"
        ).date()
    except ValueError:
        return HttpResponseBadRequest("Unreadable date.")
    task.save()
    return HttpResponse(status=204, headers={"HX-Trigger": "tasksListChanged"})


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
        if "end_date" in data:
            changes["end_date"] = (
                datetime.strptime(data["end_date"], "%Y-%m-%d").date()
                if data["end_date"]
                else None
            )
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

    # An end date that adds no days is none; one before the date is refused.
    if event.end_date and event.end_date <= event.date:
        if event.end_date < event.date:
            return HttpResponseBadRequest("The last day must be after the date.")
        event.end_date = None

    event.save()

    return _event_change_response("eventsChanged")


@login_required
@require_POST
def events_view_mode(request, mode):
    """Toggle between list and calendar view modes."""
    request.session["events_view_mode"] = mode
    request.session.modified = True
    return HttpResponse(status=204, headers={"HX-Trigger": "eventsViewChanged"})
