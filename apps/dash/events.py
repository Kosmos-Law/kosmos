"""The dash's Upcoming Events: a row of cards, one per pending event the
user may see, soonest first. An event stays until it is marked complete
or canceled, so one gone by still pending leads the row with the
past-due treatment, and today's and tomorrow's are marked as due soon.

Seven fill the capped dash's width edge to edge (16rem cards, 1rem
gaps); when fewer fit (the sidebar open) the row scrolls sideways, and
on a phone the cards stack. See static/css/apps/dash.css.
"""

from datetime import timedelta

from apps.calendar.access import events_for_user
from apps.calendar.models import Event

EVENT_LIMIT = 7


def events_context(user, today):
    return {
        "upcoming_events": events_for_user(Event.objects.all(), user)
        .filter(status="Pending", date__isnull=False)
        .select_related("matter")
        .order_by("date", "start_time", "party")[:EVENT_LIMIT],
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "yesterday": today - timedelta(days=1),
    }
