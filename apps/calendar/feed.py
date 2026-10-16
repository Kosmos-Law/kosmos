"""Events and tasks as FullCalendar entries: what the calendar's feed and
the dash's Calendar Week hand the grid."""

from datetime import datetime, timedelta


def feed_date(value):
    """The date in one of a feed's ISO date or date-time parameters."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def event_entry(event):
    """An event as a FullCalendar entry. A timed event over several days
    ends at its end time on its last day. FullCalendar's end is exclusive,
    so an all-day event over several days ends the day after its last."""
    entry = {
        "id": str(event.id),
        "title": event.calendar_title,
        "extendedProps": {
            "matter": event.matter.name if event.matter else "",
            "matter_id": event.matter.id if event.matter else None,
            "assignees": event.assignee_names,
            "event_type": event.event_type or "",
            "location": event.location or "",
            "meeting_url": event.meeting_url,
            "party": event.party or "",
            "status": event.status or "",
        },
    }
    if event.start_time and event.end_time:
        entry["start"] = f"{event.date}T{event.start_time}"
        entry["end"] = f"{event.last_date}T{event.end_time}"
        entry["allDay"] = False
    elif event.start_time:
        entry["start"] = f"{event.date}T{event.start_time}"
        entry["allDay"] = False
    else:
        entry["start"] = str(event.date)
        if event.end_date:
            entry["end"] = str(event.end_date + timedelta(days=1))
        entry["allDay"] = True

    # status-based styling
    classes = []
    if event.status == "Pending":
        classes.append("fc-event-pending")
    elif event.status == "Complete":
        classes.append("fc-event-complete")
    elif event.status == "Missed":
        classes.append("fc-event-missed")
    if not event.matter:
        classes.append("fc-event-no-matter")
    if classes:
        entry["className"] = " ".join(classes)
    return entry


def task_title(task):
    """A task's title on the calendar: its matter, then its description."""
    title = task.description or "Untitled"
    if task.matter_id:
        title = f"{task.matter.name} - {title}"
    return title


def task_entry(task, day=None, overdue=False):
    """An open task as a FullCalendar entry: an all-day entry on its due
    day (or on day, for an overdue task gathered elsewhere), told from an
    event by its id prefix and its kind, which may be dragged to another
    day but not stretched. An overdue one carries its due date, which the
    grid writes before its title, and the urgent colour."""
    classes = "fc-event-task"
    props = {"kind": "task", "task_id": task.id}
    if overdue:
        classes += " fc-event-overdue"
        props["due_label"] = f"{task.date_due:%b} {task.date_due.day}"
        props["overdue"] = True
    return {
        "id": f"task-{task.id}",
        "title": task_title(task),
        "start": str(day or task.date_due),
        "allDay": True,
        "className": classes,
        "durationEditable": False,
        "extendedProps": props,
    }
