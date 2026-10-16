"""The dash's Calendar Week: a week of the firm's calendar, Sunday to
Saturday, as a one-week slice of the calendar's month view (after Cloud
Portal's home page card). FullCalendar draws it from week_feed, and its
events drag from day to day and its days take a click to add one, as on
the calendar.

It shows the pending events the user may see, as the calendar shows them
by default; an event over several days appears on each day it covers.
With the card's Tasks toggle on (as it starts), the user's open tasks are
on their due days too, and on the week holding today any overdue from
before it are gathered on today. Past three tasks, a day's others fold
into "N more tasks", to the task list.
"""

from collections import defaultdict

from django.db.models import Q

from apps.calendar.access import events_for_user
from apps.calendar.feed import event_entry, task_entry, task_title
from apps.calendar.models import Event
from apps.tasks.constants import STATUS_COMPLETE
from apps.tasks.models import Task

# How many tasks a day shows before the rest fold into "N more tasks"
TASK_LIMIT = 3

# The session key for the card's Tasks toggle (on until switched off)
SHOW_TASKS_KEY = "dash_week_tasks"


def show_tasks(request):
    """Whether the card's Tasks toggle is on."""
    return bool(request.session.get(SHOW_TASKS_KEY, True))


def _more_tasks_entry(day, count):
    """The fold under a day's first tasks: "N more tasks", to the list."""
    return {
        "id": f"more-tasks-{day}",
        "title": f"{count} more task{'' if count == 1 else 's'}",
        "start": str(day),
        "allDay": True,
        "className": "fc-event-more-tasks",
        "editable": False,
        "extendedProps": {"kind": "more-tasks"},
    }


def _task_entries(user, first, last, today):
    """The user's open tasks due from first to last, as entries, a day's
    first three and then its fold. On the week holding today, tasks overdue
    from before it are gathered on today, ahead of today's own; each day's
    run is by title, as the calendar orders it."""
    tasks = (
        Task.objects.filter(user=user, date_due__lte=last)
        .exclude(status=STATUS_COMPLETE)
        .select_related("matter")
    )
    gather = first <= today <= last
    # the week holding today reaches back for every overdue task, however old
    if not gather:
        tasks = tasks.filter(date_due__gte=first)
    by_day = defaultdict(list)
    for task in tasks:
        overdue = task.date_due < first
        by_day[today if overdue else task.date_due].append((task, overdue))

    entries = []
    for day, on_day in by_day.items():
        on_day.sort(key=lambda pair: (not pair[1], task_title(pair[0]).lower()))
        for task, overdue in on_day[:TASK_LIMIT]:
            entries.append(task_entry(task, day=day, overdue=overdue))
        if len(on_day) > TASK_LIMIT:
            entries.append(_more_tasks_entry(day, len(on_day) - TASK_LIMIT))
    return entries


def week_feed(user, first, last, today, tasks=False):
    """The entries from first to last (inclusive) as FullCalendar takes
    them: the pending events the user may see and, with tasks, the user's
    open tasks."""
    events = (
        events_for_user(Event.objects.all(), user)
        .filter(status="Pending", date__lte=last)
        .filter(Q(end_date__gte=first) | Q(end_date=None, date__gte=first))
        .select_related("matter")
        .prefetch_related("assignees")
    )
    entries = [event_entry(event) for event in events]
    if tasks:
        entries += _task_entries(user, first, last, today)
    return entries
