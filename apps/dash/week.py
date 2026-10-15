"""The dash's Calendar Week: a week of the firm's calendar, Sunday to
Saturday, as a strip of columns (after Cloud Portal's home page card).

It shows the pending events the user may see, as the calendar shows them
by default; an event over several days appears on each day it covers.
With the card's Tasks toggle on (as it starts), the user's open tasks are on their due
days too, and on this week any overdue from before it are gathered on
today.
"""

from datetime import time, timedelta
from types import SimpleNamespace

from django.db.models import Q
from django.utils import timezone

from apps.calendar.access import events_for_user
from apps.calendar.models import Event
from apps.tasks.constants import STATUS_COMPLETE
from apps.tasks.models import Task

# How many days the strip shows: a week, Sunday first, as the calendar's
# month view has it
WEEK_DAYS = 7

# How many entries a day shows before the rest fold into a link
DAY_LIMIT = 5

# How many tasks a day shows before the rest fold into "N more tasks"
TASK_LIMIT = 3

# The session key for the card's Tasks toggle (on until switched off)
SHOW_TASKS_KEY = "dash_week_tasks"


def week_start(day):
    """The Sunday on or before the day: the first day of its week."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


def short_time(value):
    """A time as the calendar's month view writes it: 9:30a, 1p."""
    hour = value.hour % 12 or 12
    minutes = f":{value.minute:02d}" if value.minute else ""
    return f"{hour}{minutes}{'a' if value.hour < 12 else 'p'}"


def _event_entry(event):
    """An event as the strip shows it: the calendar's title, and its
    start time (None for an all-day event)."""
    return SimpleNamespace(
        kind="event",
        id=event.id,
        title=event.calendar_title,
        time=event.start_time,
        time_label=short_time(event.start_time) if event.start_time else "",
        overdue=False,
        first_day=event.date,
        last_day=event.last_date,
    )


def _task_entry(task, today, gather_overdue):
    """An open task as the strip shows it, on its due day, titled as the
    calendar titles it. On this week, a task overdue from before it is
    gathered on today, marked overdue and dated."""
    day, overdue = task.date_due, False
    if gather_overdue and day < week_start(today):
        day, overdue = today, True
    title = task.description or "Untitled"
    if task.matter_id:
        title = f"{task.matter.name} - {title}"
    return SimpleNamespace(
        kind="task",
        id=task.id,
        title=title,
        time=None,
        time_label=f"{task.date_due:%b} {task.date_due.day}" if overdue else "",
        overdue=overdue,
        first_day=day,
        last_day=day,
    )


def _entry_key(entry):
    """Gathered overdue tasks first, then all-day events, then the day's
    tasks, then timed events by time, each run by title."""
    return (
        not entry.overdue,
        entry.time is not None,
        entry.time or time.min,
        entry.kind != "event",
        entry.title.lower(),
    )


def week_days(user, first, today, show_tasks=False):
    """The seven days from first, each with the entries the strip shows on
    it: its date, its label (the weekday, short), whether it is today, the
    entries that fit, and how many more there are. Past its first three
    tasks, a day's tasks fold into a count of their own."""
    last = first + timedelta(days=WEEK_DAYS - 1)
    events = (
        events_for_user(Event.objects.all(), user)
        .filter(status="Pending", date__lte=last)
        .filter(Q(end_date__gte=first) | Q(end_date=None, date__gte=first))
        .select_related("matter")
        .prefetch_related("assignees")
    )
    entries = [_event_entry(event) for event in events]
    if show_tasks:
        is_current = first == week_start(today)
        tasks = (
            Task.objects.filter(user=user, date_due__lte=last)
            .exclude(status=STATUS_COMPLETE)
            .select_related("matter")
        )
        # this week reaches back for every overdue task, however old
        if not is_current:
            tasks = tasks.filter(date_due__gte=first)
        entries += [_task_entry(task, today, is_current) for task in tasks]
    entries.sort(key=_entry_key)

    days = []
    for offset in range(WEEK_DAYS):
        day = first + timedelta(days=offset)
        on_day = [e for e in entries if e.first_day <= day <= e.last_day]
        tasks = [e for e in on_day if e.kind == "task"]
        folded = {id(e) for e in tasks[TASK_LIMIT:]}
        shown = [e for e in on_day if id(e) not in folded]
        days.append(
            SimpleNamespace(
                date=day,
                label=day.strftime("%a"),
                is_today=day == today,
                entries=shown[:DAY_LIMIT],
                more=max(len(shown) - DAY_LIMIT, 0),
                more_tasks=len(folded),
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


def show_tasks(request):
    """Whether the card's Tasks toggle is on."""
    return bool(request.session.get(SHOW_TASKS_KEY, True))


def week_context(user, week_of=None, today=None, tasks=False):
    """What the Calendar Week shows for the week holding week_of (today's
    week by default): its days, how many entries they hold, its span, and
    the weeks either side for the chevrons; with tasks, the user's open
    tasks among them."""
    today = today or timezone.localdate()
    first = week_start(week_of or today)
    week = week_days(user, first, today, show_tasks=tasks)
    return {
        "week": week,
        "week_tasks": tasks,
        "week_first": first,
        "week_count": sum(day.count for day in week),
        "week_range": week_range(first, today),
        "week_is_current": first == week_start(today),
        "week_today": today,
        "week_previous": first - timedelta(days=WEEK_DAYS),
        "week_next": first + timedelta(days=WEEK_DAYS),
    }
