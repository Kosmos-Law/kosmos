"""Sending event notifications (utils.notify), by email or ntfy as each
one says.

A notification is due once its time has come and it has not been sent for
that time. The time is worked out from the event as it stands now, so an
event that moves is notified again at its new time, and one whose time
passed long ago (a notification added late, or an event moved into the
past) is let go rather than sent stale.

The event-reminders schedule (apps/management/schedules.py) runs send_due
every minute.
"""

from datetime import timedelta

from django.utils import timezone

from apps.calendar.models import EventReminder
from utils import notify

# How long after its time a notification is still worth sending
GRACE = timedelta(hours=2)


def due_reminders(queryset, now=None):
    """The notifications in the queryset to send now, as (reminder, fire_at)
    pairs. Ones too old to send are marked as passed instead."""
    now = now or timezone.now()
    due = []
    for reminder in queryset:
        fire_at = reminder.fire_at
        if fire_at is None or fire_at > now or reminder.sent_for == fire_at:
            continue
        if now - fire_at > GRACE:
            EventReminder.objects.filter(pk=reminder.pk).update(sent_for=fire_at)
            continue
        due.append((reminder, fire_at))
    return due


def send_due(now=None):
    """Send every event notification that is due. Returns (sent, errors)."""
    queryset = EventReminder.objects.select_related(
        "user", "event", "event__matter"
    ).filter(user__is_active=True)
    sent = errors = 0
    for reminder, fire_at in due_reminders(queryset, now):
        result = notify.event_reminder(reminder.user, reminder.event, reminder.channel)
        if result["success"]:
            EventReminder.objects.filter(pk=reminder.pk).update(sent_for=fire_at)
            sent += 1
        else:
            errors += 1
    return sent, errors
