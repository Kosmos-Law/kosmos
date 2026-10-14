"""Notifications: an event reminder, sent by one of two channels
(utils.models.CHANNEL_CHOICES). Each notification on an event names its
own; the user's choice in Settings (CustomUser.notify_by) is the default
for new ones.

By ntfy, a notification is pushed to the topic the user's ntfy app is
subscribed to (https://docs.ntfy.sh/publish/), arriving in seconds, with
an Open button that opens the calendar. When ntfy cannot be reached the
notification goes by email instead, so one is not lost to an outage.

By email, it is a short plain-text message to the user's address.

A machine other than production (settings.NOT_PRODUCTION) pushes to each
topic with a suffix (settings.NTFY_TOPIC_SUFFIX), so it has a channel of
its own even with a copy of production's data, marks its titles
(NOTIFY_TITLE_PREFIX), and sends no notification email
(EMAIL_NOTIFICATIONS): a refreshed dev machine never doubles production's
notifications.

Each sender returns {"success": bool, "error": str}, for
apps.calendar.reminders.send_due.
"""

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from utils.links import absolute

logger = logging.getLogger(__name__)


# --- ntfy -------------------------------------------------------------------


def ntfy_ready(user):
    """Whether the user has a topic to push to: one is made when they first
    choose Push in Settings."""
    return bool(user.ntfy_topic)


def topic(user):
    """The topic this machine pushes the user's notifications to: theirs,
    with this machine's suffix (-dev on the dev machine)."""
    return user.ntfy_topic + settings.NTFY_TOPIC_SUFFIX


def push(user, title, message, *, priority=3, tags=(), click=None, actions=()):
    """Publish one message to the user's ntfy topic. Returns
    {"success": bool, "error": str}."""
    body = {
        "topic": topic(user),
        "title": settings.NOTIFY_TITLE_PREFIX + title,
        "message": message,
        "priority": priority,
        "tags": list(tags),
    }
    if click:
        body["click"] = click
    if actions:
        body["actions"] = list(actions)
    headers = {}
    if user.ntfy_token:
        headers["Authorization"] = f"Bearer {user.ntfy_token}"
    try:
        response = requests.post(
            user.ntfy_server.rstrip("/"), json=body, headers=headers, timeout=10
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logger.warning("ntfy push to %s failed: %s", user.ntfy_server, error)
        return {"success": False, "error": str(error)}
    return {"success": True}


def _site(path):
    """The absolute address of a page, or None when the site has no public
    address set: a phone cannot open a bare path."""
    url = absolute(path)
    return url if url.startswith("http") else None


def _deliver(user, channel, *, pushed, emailed):
    """Send one notification the way its channel says: by ntfy it is
    pushed, falling back to email if the push fails or ntfy is not set up;
    by email it is emailed. Where email notifications are off (the dev
    machine), nothing is emailed, and the notification counts as handled
    so it is not tried again every minute."""
    if channel == "ntfy" and ntfy_ready(user):
        result = pushed()
        if result["success"]:
            return result
        if not settings.EMAIL_NOTIFICATIONS:
            return result
        logger.info("Falling back to email for %s", user)
    if not settings.EMAIL_NOTIFICATIONS:
        logger.info("Email notifications are off here; not emailing %s", user)
        return {"success": True, "skipped": "email off"}
    return emailed()


# --- what is sent -------------------------------------------------------------


def _day(day):
    return day.strftime("%A, %B %-d")


def _clock(at):
    return at.strftime("%-I:%M %p")


def event_title(event):
    return event.description or "Event"


def event_when(event):
    """The event's day and time in words: "Tuesday, October 20 at 2:00 PM
    – 3:00 PM", or the day alone for an all-day event."""
    text = _day(event.date)
    if event.start_time:
        text += " at " + _clock(event.start_time)
        if event.end_time:
            text += " – " + _clock(event.end_time)
    return text


def event_lines(event):
    """The notification's text, one line each: when, through which day
    for an event over several days, the matter, the location."""
    lines = [event_when(event)]
    if event.end_date:
        lines.append(f"Through {_day(event.end_date)}")
    if event.matter_id:
        lines.append(event.matter.name)
    if event.location:
        lines.append(event.location)
    return lines


def send_event_email(user, event):
    """The notification by email. Returns {"success", "error"}."""
    if not user.email:
        return {"success": False, "error": "The user has no email address."}
    subject = f"{event_title(event)} - {event_when(event)}"
    lines = [event_title(event), ""]
    lines.append(f"When: {event_when(event)}")
    if event.end_date:
        lines.append(f"Through: {_day(event.end_date)}")
    if event.matter_id:
        lines.append(f"Matter: {event.matter.name}")
    if event.location:
        lines.append(f"Location: {event.location}")
    calendar_page = _site(reverse("calendar:index"))
    if calendar_page:
        lines += ["", calendar_page]
    lines += ["", "-- Kosmos"]
    try:
        send_mail(subject, "\n".join(lines), None, [user.email])
    except Exception as error:
        logger.warning("Event notification email to %s failed: %s", user.email, error)
        return {"success": False, "error": str(error)}
    return {"success": True}


def event_reminder(user, event, channel=None):
    """An event's notification, by the channel named or the user's default."""

    def pushed():
        calendar_page = _site(reverse("calendar:index"))
        actions = (
            [{"action": "view", "label": "Open", "url": calendar_page}]
            if calendar_page
            else []
        )
        return push(
            user,
            event_title(event),
            "\n".join(event_lines(event)),
            priority=4,
            tags=["date"],
            click=calendar_page,
            actions=actions,
        )

    return _deliver(
        user,
        channel or user.notify_by,
        pushed=pushed,
        emailed=lambda: send_event_email(user, event),
    )


def test_message(user):
    """A test push from Settings, so the user can see their phone is set up."""
    return push(
        user,
        "Kosmos: notifications are working",
        "Event notifications will arrive here.",
        priority=3,
        tags=["white_check_mark"],
        click=_site(reverse("settings:notifications-index")),
    )
