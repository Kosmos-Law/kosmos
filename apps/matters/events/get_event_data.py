from datetime import datetime, timedelta

from django.utils import timezone

from apps.calendar.models import Event
from apps.case.facts.sorting import sort_keys, stored_sort_key
from apps.matters.proceedings.models import Proceeding

# The columns the matter Events tab sorts by: the list's own sort buttons.
# The stored key is checked against these on the way in and on the way out,
# so a session cannot hand `order_by()` a name the model does not have.
SORT_FIELDS = ("date", "party", "description", "status")
SORT_KEYS = sort_keys(SORT_FIELDS)
DEFAULT_SORT = "date"


def sort_session_key(matter_id):
    return f"matter_events_sort_{matter_id}"


def get_event_data(request, matter):
    proceeding = Proceeding.objects.filter(matter=matter.id, primary=True).first()
    third_day = timezone.localdate() + timedelta(days=3)

    # Get filter status from session, default to "Pending"
    status_session_key = f"matter_events_filter_{matter.id}"
    filter_status = request.session.get(status_session_key, "Pending")

    order_by = stored_sort_key(
        {"order_by": request.session.get(sort_session_key(matter.id))},
        SORT_KEYS,
        DEFAULT_SORT,
    )

    # Build queryset based on filter
    events = Event.objects.filter(matter=matter)
    if filter_status:
        events = events.filter(status=filter_status)

    events = events.order_by(order_by)

    # Calculate duration for events
    for event in events:
        if event.start_time and event.end_time:
            start = datetime.combine(datetime.today(), event.start_time)
            end = datetime.combine(datetime.today(), event.end_time)
            duration_delta = end - start
            event.duration = duration_delta.total_seconds() / 3600
        else:
            event.duration = None

    # Get current order without the "-" prefix for template comparison
    current_order = order_by.lstrip("-")

    event_data = {
        "matter": matter,
        "proceeding": proceeding,
        "events": events,
        "events_filter_status": filter_status,
        "current_order": current_order,
        "third_day": third_day,
    }

    return event_data
