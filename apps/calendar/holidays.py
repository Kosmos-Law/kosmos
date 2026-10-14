"""US federal holidays: shown on the calendar beside the firm's events,
and counted as court holidays by the deadline calculator.

The dates come from the holidays package, which knows the observed day
when a holiday falls on a weekend (Independence Day on a Saturday is
observed the Friday before).
"""

from datetime import timedelta

import holidays as holidays_lib

COUNTRY = "US"


def between(first, last):
    """The federal holidays from one day to another, inclusive, as
    (day, name) pairs in date order."""
    years = range(first.year, last.year + 1)
    calendar = holidays_lib.country_holidays(COUNTRY, years=years, observed=True)
    return [
        (day, name) for day, name in sorted(calendar.items()) if first <= day <= last
    ]


def name_of(day):
    """The holiday's name when the day is one, else None."""
    return holidays_lib.country_holidays(COUNTRY, years=day.year, observed=True).get(
        day
    )


def is_court_day(day):
    """Whether the courts sit: a weekday that is not a federal holiday."""
    return day.weekday() < 5 and name_of(day) is None


def next_court_day(day):
    """The first court day on or after the day."""
    while not is_court_day(day):
        day += timedelta(days=1)
    return day


def feed(first, last):
    """The federal holidays between two days, as FullCalendar events:
    read-only all-day entries that open nothing."""
    return [
        {
            "id": f"holiday-{day.isoformat()}",
            "title": name,
            "start": day.isoformat(),
            "allDay": True,
            "className": "fc-event-holiday",
            "editable": False,
            "extendedProps": {"kind": "holiday"},
        }
        for day, name in between(first, last)
    ]
