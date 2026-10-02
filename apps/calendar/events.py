from datetime import datetime, time, timedelta
from logging import getLogger

from apps.calendar.filter import EventFilter
from apps.management.pagination import CustomPaginator

logger = getLogger(__name__)

SESSION_KEY = "events_filter"

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


def toolbar_context(request, filter=None):
    """What the toolbar's status, assignee and matter menus show. A saved
    value the user has no choice for (a matter that is not theirs) shows as
    no selection, which is also how the filter treats it."""
    filter = filter or event_filter(request)
    assigned_value = filter.data.get("assigned_to") or ""
    matter_value = filter.data.get("matter") or ""
    assigned_label = dict(filter.assigned_choices).get(assigned_value, "")
    matter_label = dict(filter.matter_choices).get(matter_value, "")
    return {
        "events_filter_status": filter.data.get("status") or "",
        "events_filter_assigned": assigned_label,
        "events_filter_assigned_value": assigned_value if assigned_label else "",
        "events_filter_matter": matter_label,
        "events_filter_matter_value": matter_value if matter_label else "",
        "matters": filter.matters,
        "users": filter.users,
    }


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

    # Calculate duration for each event
    event_list = pagination.get_object_list()
    for event in event_list:
        if event.start_time and event.end_time:
            # Combine times with a date to do time arithmetic
            start = datetime.combine(datetime.today(), event.start_time)
            end = datetime.combine(datetime.today(), event.end_time)
            duration_delta = end - start
            # Convert to hours (as a float for fractional hours)
            event.duration = duration_delta.total_seconds() / 3600
        else:
            event.duration = None

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
