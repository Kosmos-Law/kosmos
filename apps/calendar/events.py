from datetime import datetime, time, timedelta
from logging import getLogger

from apps.calendar.filter import EventFilter, assignee_tokens
from apps.management.pagination import CustomPaginator

logger = getLogger(__name__)

SESSION_KEY = "events_filter"
SHOW_TASKS_KEY = "events_show_tasks"
SHOW_HOLIDAYS_KEY = "events_show_holidays"

DEFAULT_FILTER = {
    "status": "Pending",
    "matter": None,
    "date_min": "",
    "date_max": "",
    "party": None,
    "order_by": "date",
}


def saved_filter(request):
    """The filter saved in the session, or the default when none is saved.

    Restore Defaults empties the saved filter. Every reader (the list, the
    calendar feed, the toolbar) comes through here, so an emptied filter
    means Pending events in both views rather than every status in one.
    """
    data = request.session.get(SESSION_KEY)
    if not data:
        data = dict(DEFAULT_FILTER)
        request.session[SESSION_KEY] = data
        request.session.modified = True
    return data


def event_filter(request):
    """The saved filter applied to the events this user may see."""
    return EventFilter(saved_filter(request), user=request.user)


def filter_is_active(request):
    """Whether the saved filter differs from the default, for the menu's
    Filter row."""
    return saved_filter(request) != DEFAULT_FILTER


# The overlays as the calendar starts: holidays on, tasks off. The menu's
# button reads as selected only while the user has moved off these.
DEFAULT_SHOW_TASKS = False
DEFAULT_SHOW_HOLIDAYS = True


def show_tasks(request):
    """Whether the calendar shows the user's open tasks beside the events."""
    return bool(request.session.get(SHOW_TASKS_KEY, DEFAULT_SHOW_TASKS))


def show_holidays(request):
    """Whether the calendar shows US federal holidays beside the events."""
    return bool(request.session.get(SHOW_HOLIDAYS_KEY, DEFAULT_SHOW_HOLIDAYS))


def menu_is_active(request):
    """Whether the calendar's menu holds anything off its defaults: a
    filter set, or an overlay switched from how it starts."""
    return (
        filter_is_active(request)
        or show_tasks(request) != DEFAULT_SHOW_TASKS
        or show_holidays(request) != DEFAULT_SHOW_HOLIDAYS
    )


def assignees_label(names):
    """The Assigned-to button's text: nothing ticked reads as all, one or
    two by name, more by their number."""
    if not names:
        return ""
    if len(names) <= 2:
        return ", ".join(names)
    return f"{len(names)} assignees"


MATTER_VIEW_MODE_KEY = "matter_events_view_mode"


def matter_menu_context(request, matter):
    """The calendar menu's state on a matter's Events tab: the overlays
    (shared with the main calendar) and the tab's own list-or-calendar
    choice, kept across matters. The tab has no filter, so the menu's
    button reads as set only when an overlay is off its default."""
    return {
        "matter": matter,
        "show_tasks": show_tasks(request),
        "show_holidays": show_holidays(request),
        "menu_active": (
            show_tasks(request) != DEFAULT_SHOW_TASKS
            or show_holidays(request) != DEFAULT_SHOW_HOLIDAYS
        ),
        "view_mode": request.session.get(MATTER_VIEW_MODE_KEY, "calendar"),
    }


def toolbar_context(request, filter=None):
    """What the toolbar's status, assignee and matter menus show. A saved
    value the user has no choice for (a matter that is not theirs) shows as
    no selection, which is also how the filter treats it."""
    filter = filter or event_filter(request)
    matter_value = filter.data.get("matter") or ""
    matter_label = dict(filter.matter_choices).get(matter_value, "")
    # The assignees ticked, in the menu's order, less any that is no
    # longer a choice (a user since deactivated)
    choices = dict(filter.assigned_choices)
    ticked = [
        token
        for token in assignee_tokens(filter.data.get("assigned_to"))
        if token in choices
    ]
    return {
        "events_filter_status": filter.data.get("status") or "",
        "events_filter_assigned": assignees_label([choices[t] for t in ticked]),
        "events_filter_assigned_values": ticked,
        "events_filter_matter": matter_label,
        "events_filter_matter_value": matter_value if matter_label else "",
        "matters": filter.matters,
        "users": filter.users,
        "show_tasks": show_tasks(request),
        "show_holidays": show_holidays(request),
        "filter_active": filter_is_active(request),
        "menu_active": menu_is_active(request),
        "view_mode": request.session.get("events_view_mode", "calendar"),
    }


def annotate_durations(events):
    """Set each event's duration for a list's Duration column: ``duration_days``
    for an event over several days, ``duration`` in hours for a timed event
    on one day, neither for an all-day event."""
    for event in events:
        event.duration = None
        event.duration_days = None
        if event.end_date:
            event.duration_days = (event.end_date - event.date).days + 1
        elif event.start_time and event.end_time:
            # Combine times with a date to do time arithmetic
            start = datetime.combine(datetime.min, event.start_time)
            end = datetime.combine(datetime.min, event.end_time)
            # Convert to hours (as a float for fractional hours)
            event.duration = (end - start).total_seconds() / 3600
    return events


def default_end_time(start_time):
    """The end time for an event saved with a start and no end: an hour
    later, kept on the same day. An event has one date, so an end past
    midnight would read as before the start. A start in the last minute of
    the day has no later time to end at and gets none."""
    start = datetime.combine(datetime.min, start_time)
    end = start + timedelta(hours=1)
    if end.date() == start.date():
        return end.time()
    last_minute = time(23, 59)
    return last_minute if start_time < last_minute else None


def get_table_data(request):
    table_data = {}

    filter = event_filter(request)
    events = filter.qs

    pagination = CustomPaginator(
        events, per_page=10, request=request, session_key="events_pagination"
    )

    event_list = pagination.get_object_list()
    annotate_durations(event_list)

    current_order = filter.data.get("order_by", "date")
    if isinstance(current_order, list):
        current_order = current_order[0] if current_order else "date"
    current_order = current_order.lstrip("-")

    table_data["pagination"] = pagination
    table_data["session_key"] = "events_pagination"
    table_data["trigger_key"] = "eventsChanged"
    table_data["objects"] = event_list
    table_data["current_order"] = current_order

    return table_data | toolbar_context(request, filter)
