"""The dash's calendar card: a week of the firm's calendar, Sunday to
Saturday, as a strip of columns (after Cloud Portal's home page card).

It shows the pending events the user may see, as the calendar shows them
by default; an event over several days appears on each day it covers.
"""

from datetime import time, timedelta
from types import SimpleNamespace

from django.db.models import Q
from django.utils import timezone

from apps.calendar.access import events_for_user
from apps.calendar.models import Event

# How many days the strip shows: a week, Sunday first, as the calendar's
# month view has it
WEEK_DAYS = 7

# How many entries a day shows before the rest fold into a link
DAY_LIMIT = 5


def week_start(day):
    """The Sunday on or before the day: the first day of its week."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def short_time(value):
    """A time as the calendar's month view writes it: 9:30a, 1p."""
    hour = value.hour % 12 or 12
    minutes = f":{value.minute:02d}" if value.minute else ""
    return f"{hour}{minutes}{'a' if value.hour < 12 else 'p'}"


def _entry_key(event):
    """All-day events first, then by start time, then by title."""
    return (
        event.start_time is not None,
        event.start_time or time.min,
        event.calendar_title.lower(),
    )


def week_days(user, first, today):
    """The seven days from first, each with the events the strip shows on
    it: its date, its label (the weekday, short), whether it is today, the
    entries that fit, and how many more there are."""
    last = first + timedelta(days=WEEK_DAYS - 1)
    events = (
        events_for_user(Event.objects.all(), user)
        .filter(status="Pending", date__lte=last)
        .filter(Q(end_date__gte=first) | Q(end_date=None, date__gte=first))
        .select_related("matter")
        .prefetch_related("assignees")
    )
    entries = sorted(events, key=_entry_key)
    for event in entries:
        event.time_label = short_time(event.start_time) if event.start_time else ""

    days = []
    for offset in range(WEEK_DAYS):
        day = first + timedelta(days=offset)
        on_day = [e for e in entries if e.date <= day <= e.last_date]
        days.append(
            SimpleNamespace(
                date=day,
                label=day.strftime("%a"),
                is_today=day == today,
                entries=on_day[:DAY_LIMIT],
                more=max(len(on_day) - DAY_LIMIT, 0),
                count=len(on_day),
            )
        )
    return days


def week_range(first, today):
    """The week's span for the card's heading: Oct 11 – 17, or Oct 25 –
    Nov 1 when it crosses a month, with the year when it is not this one."""
    last = first + timedelta(days=WEEK_DAYS - 1)
    end = f"{last.day}" if last.month == first.month else f"{last:%b} {last.day}"
    span = f"{first:%b} {first.day} – {end}"
    if last.year != today.year or first.year != today.year:
        span += f", {last.year}"
    return span


def week_context(user, week_of=None, today=None):
    """What the calendar card shows for the week holding week_of (today's
    week by default): its days, how many entries they hold, its span, and
    the weeks either side for the chevrons."""
    today = today or timezone.localdate()
    first = week_start(week_of or today)
    week = week_days(user, first, today)
    return {
        "week": week,
        "week_first": first,
        "week_count": sum(day.count for day in week),
        "week_range": week_range(first, today),
        "week_is_current": first == week_start(today),
        "week_today": today,
        "week_previous": first - timedelta(days=WEEK_DAYS),
        "week_next": first + timedelta(days=WEEK_DAYS),
    }
