"""JSON API for the calendar, for another app to overlay Kosmos's events
on its own calendar (Cloud Portal does). Auth is the user's X-Kosmos-Token
key (CompanionToken, via kosmos_api_auth), the one the Claude Desktop page
in Settings issues, so the events returned are the ones that user may see.

GET events/api/?start=YYYY-MM-DD&end=YYYY-MM-DD returns the events on those
days, inclusive, as a list of objects:

    id, title (matter - description - initials, as the calendar shows it),
    date, end_date (null), start_time and end_time ("HH:MM:SS" or null),
    all_day, matter, location, status, event_type, url (the event in
    Kosmos), and the firm's time_zone, which the times are in.
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.calendar.access import events_for_user
from apps.calendar.models import Event
from apps.drafts.api_auth import kosmos_api_auth

RANGE_LIMIT_DAYS = 400


def _day(value, default):
    if not value:
        return default
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def event_title(event):
    parts = []
    if event.matter:
        parts.append(event.matter.name)
    parts.append(event.description or "Untitled")
    if event.assigned_to and event.assigned_to.initials:
        parts.append(event.assigned_to.initials)
    return " - ".join(parts)


def event_row(event, request):
    return {
        "id": event.id,
        "title": event_title(event),
        "date": event.date.isoformat() if event.date else None,
        "end_date": None,
        "start_time": event.start_time.isoformat() if event.start_time else None,
        "end_time": event.end_time.isoformat() if event.end_time else None,
        "all_day": not event.start_time,
        "matter": event.matter.name if event.matter else "",
        "location": event.location or "",
        "status": event.status or "",
        "event_type": event.event_type or "",
        "url": request.build_absolute_uri(f"/events/{event.id}/edit"),
    }


@require_GET
@kosmos_api_auth
def api_events(request):
    today = timezone.localdate()
    try:
        start = _day(request.GET.get("start"), today - timedelta(days=30))
        end = _day(request.GET.get("end"), today + timedelta(days=60))
    except ValueError:
        return JsonResponse({"error": "start and end must be ISO dates."}, status=400)
    if end < start:
        return JsonResponse({"error": "end is before start."}, status=400)
    if (end - start).days > RANGE_LIMIT_DAYS:
        return JsonResponse(
            {"error": f"The range may cover at most {RANGE_LIMIT_DAYS} days."},
            status=400,
        )

    events = (
        events_for_user(Event.objects.all(), request.api_user)
        .filter(date__gte=start, date__lte=end)
        .select_related("matter", "assigned_to")
        .order_by("date", "start_time", "id")
    )
    return JsonResponse(
        {
            "time_zone": settings.TIME_ZONE,
            "events": [event_row(event, request) for event in events],
        }
    )
