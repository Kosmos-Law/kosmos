"""Calendar invitations, both ways (after Cloud Portal's).

Forwarded in: an invitation is an email with an iCalendar attachment. A
firm user forwards it to the firm's calendar address
(settings.CALENDAR_INBOUND_ADDRESS); the shared Mailgun route posts the
parsed message to the inbound webhook (apps.intakes.inbound), which hands
it here. The attachment is read and posted as a firm event: no assignees,
so it is everyone's. The invitation's UID is kept on the event, so a later
revision of the same invitation updates it and a cancellation removes it.

Sent out: an event's guests (EventGuest), people outside the firm, are
emailed an invitation of the same kind (METHOD:REQUEST), which any
calendar app shows with Yes, Maybe and No. The organiser named in it is
the calendar address, so a guest's answer, an email with a METHOD:REPLY
attachment that their calendar app sends on its own, comes back through
the same webhook and is recorded on the guest. A change to the event goes
out again as a new revision (SEQUENCE); a deleted event, or a guest
removed, gets a cancellation (METHOD:CANCEL). People in the firm are not
guests: they are the event's assignees.
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    timedelta,
    timezone as dt_timezone,
)
from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.utils import timezone
from icalendar import (
    Calendar,
    Event as VEvent,
    vCalAddress,
    vText,
)

from apps.accounts.models import CustomUser
from apps.calendar import sync
from apps.calendar.events import default_end_time
from apps.calendar.models import Event

logger = logging.getLogger(__name__)

PRODID = "-//Kosmos//Calendar//EN"
UTC = dt_timezone.utc
ANSWERS = {"accepted", "declined", "tentative"}

# Mail providers anyone may have an address at: a firm whose own email is
# at one of these has no domain of its own to keep guests off
PUBLIC_DOMAINS = {
    "aol.com",
    "gmail.com",
    "googlemail.com",
    "hotmail.com",
    "icloud.com",
    "live.com",
    "me.com",
    "outlook.com",
    "proton.me",
    "protonmail.com",
    "yahoo.com",
}


def calendar_address():
    """The firm's calendar address, or "" while the feature is off."""
    return settings.CALENDAR_INBOUND_ADDRESS


def is_calendar_recipient(recipient):
    """Whether a message was sent to the calendar address."""
    address = calendar_address()
    return bool(address) and parseaddr(recipient)[1].lower() == address


def can_invite():
    return bool(calendar_address())


def _firm():
    from apps.settings.models import Firm

    return Firm.objects.first()


def firm_name():
    firm = _firm()
    return (firm.name if firm else "") or "Kosmos"


# --- the guard --------------------------------------------------------------


def firm_member(email):
    """Whether an address is the firm's own: an active user's, the firm's
    listed addresses, or any on the firm's own email domain. Such a person
    is an assignee, not a guest. Returns what to call them, or None."""
    email = email.strip().lower()
    user = CustomUser.objects.filter(email__iexact=email, is_active=True).first()
    if user is not None:
        return user.full_name
    firm = _firm()
    if firm is None:
        return None
    listed = {
        a.lower() for a in (firm.email, firm.billing_email, firm.intake_email) if a
    }
    if email in listed:
        return email
    domain = firm.email.rpartition("@")[2].lower() if firm.email else ""
    if domain and domain not in PUBLIC_DOMAINS and email.endswith(f"@{domain}"):
        return email
    return None


# --- reading an invitation --------------------------------------------------


@dataclass
class Invitation:
    uid: str
    sequence: int
    cancelled: bool
    summary: str
    location: str
    date: date
    end_date: date | None
    start_time: object
    end_time: object


def calendar_text(post, files):
    """The iCalendar text in a posted message: the .ics attachment, or a
    calendar block in the body. None when there is neither."""
    for upload in files.values():
        name = (upload.name or "").lower()
        if upload.content_type == "text/calendar" or name.endswith(".ics"):
            return upload.read().decode("utf-8", "replace")
    for value in post.values():
        start = value.find("BEGIN:VCALENDAR")
        if start != -1:
            end = value.find("END:VCALENDAR", start)
            if end != -1:
                return value[start : end + len("END:VCALENDAR")]
    return None


def _local(value):
    """A date stays a date; a datetime becomes a naive one in the firm's
    zone, which is how events keep their times. One with no zone of its
    own is taken to be in it already."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = timezone.localtime(value)
        return value.replace(tzinfo=None)
    return value


def parse_invitation(text):
    """The first event in iCalendar text, or None when there is none."""
    calendar = Calendar.from_ical(text)
    events = list(calendar.walk("VEVENT"))
    if not events:
        return None
    vevent = events[0]

    method = str(calendar.get("METHOD", "")).upper()
    status = str(vevent.get("STATUS", "")).upper()

    start = _local(vevent.get("DTSTART").dt)
    end_property = vevent.get("DTEND")
    end = _local(end_property.dt) if end_property is not None else None
    duration = vevent.get("DURATION")
    if end is None and duration is not None:
        end = start + duration.dt

    if isinstance(start, datetime):
        event_date, start_time = start.date(), start.time()
        if not isinstance(end, datetime) or end <= start:
            end = datetime.combine(
                event_date, default_end_time(start_time) or start_time
            )
        end_date = end.date() if end.date() > event_date else None
        end_time = end.time()
    else:
        # All-day: the iCalendar end is the day after the last day
        event_date, start_time, end_time, end_date = start, None, None, None
        if isinstance(end, date):
            last = end - timedelta(days=1)
            if last > event_date:
                end_date = last

    return Invitation(
        uid=str(vevent.get("UID", "")).strip(),
        sequence=int(vevent.get("SEQUENCE", 0) or 0),
        cancelled=method == "CANCEL" or status == "CANCELLED",
        summary=str(vevent.get("SUMMARY", "")).strip(),
        location=str(vevent.get("LOCATION", "")).strip(),
        date=event_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
    )


def _fit(value, field):
    return value[: Event._meta.get_field(field).max_length]


def post_invitation(user, invitation):
    """Put the invitation on the firm's calendar as a firm event.

    Returns (outcome, event): 'created' or 'updated' with the event;
    'cancelled' with the event just removed; 'stale' when an older revision
    of an invitation already posted arrives; 'missing' for a cancellation
    of an event that is not here.
    """
    existing = None
    if invitation.uid:
        existing = Event.objects.filter(ical_uid=invitation.uid).first()

    if invitation.cancelled:
        if existing is None:
            return "missing", None
        sync.delete_event_remote(existing)
        existing.delete()
        return "cancelled", existing

    if existing is not None and invitation.sequence < existing.ical_sequence:
        return "stale", existing

    event = existing or Event(user=user, status="Pending", ical_uid=invitation.uid)
    event.description = _fit(invitation.summary or "Untitled", "description")
    event.date = invitation.date
    event.end_date = invitation.end_date
    event.start_time = invitation.start_time
    event.end_time = invitation.end_time
    event.location = _fit(invitation.location, "location") or None
    event.ical_sequence = invitation.sequence
    event.save()
    sync.push_event(event)
    return ("updated" if existing else "created"), event


# --- inviting guests --------------------------------------------------------


def details(event):
    """What the guests were told: a change to any of it sends the
    invitation again."""
    return (
        event.date,
        event.end_date,
        event.start_time,
        event.end_time,
        event.description,
        event.location,
    )


def _ensure_uid(event):
    if not event.invite_uid:
        domain = calendar_address().rpartition("@")[2] or "kosmos"
        event.invite_uid = f"{uuid.uuid4()}@{domain}"
        event.save(update_fields=["invite_uid"])


def _vevent(event, guests, method, organiser):
    vevent = VEvent()
    vevent.add("uid", event.invite_uid)
    vevent.add("sequence", event.invite_sequence)
    vevent.add("dtstamp", datetime.now(UTC))
    vevent.add("summary", event.description or "Untitled")
    if event.location:
        vevent.add("location", event.location)
    if event.start_time:
        # A moment, given in UTC, which every calendar app reads
        start = event.start_at
        end = event.end_at if event.end_at and event.end_at > start else None
        vevent.add("dtstart", start.astimezone(UTC))
        vevent.add("dtend", (end or start + timedelta(hours=1)).astimezone(UTC))
    else:
        # All-day: the iCalendar end is the day after the last day
        vevent.add("dtstart", event.date)
        vevent.add("dtend", event.last_date + timedelta(days=1))
    vevent.add("status", "CANCELLED" if method == "CANCEL" else "CONFIRMED")
    address = vCalAddress(f"mailto:{calendar_address()}")
    address.params["CN"] = vText(organiser)
    vevent.add("organizer", address, encode=0)
    for guest in guests:
        attendee = vCalAddress(f"mailto:{guest.email}")
        if guest.name:
            attendee.params["CN"] = vText(guest.name)
        attendee.params["ROLE"] = vText("REQ-PARTICIPANT")
        attendee.params["PARTSTAT"] = vText(guest.status.upper())
        attendee.params["RSVP"] = vText("TRUE")
        vevent.add("attendee", attendee, encode=0)
    return vevent


def calendar_text_for(event, guests, method, organiser):
    """The iCalendar text sent to the guests: a request, or a
    cancellation."""
    calendar = Calendar()
    calendar.add("prodid", PRODID)
    calendar.add("version", "2.0")
    calendar.add("method", method)
    calendar.add_component(_vevent(event, guests, method, organiser))
    return calendar.to_ical().decode()


def when(event):
    """The event's day and time, written out for the email."""
    text = event.date.strftime("%A, %B %-d, %Y")
    if event.end_date:
        text += event.end_date.strftime(" to %A, %B %-d, %Y")
    if event.start_time:
        text += " at " + event.start_time.strftime("%-I:%M %p")
        if event.end_time:
            text += " to " + event.end_time.strftime("%-I:%M %p")
    return text


def _send(event, guests, method, subject, intro, user):
    """Email each guest the calendar text, as the alternative part a mail
    client reads as an invitation and as an attachment. Sent from the
    site's address in the user's name, with replies to the calendar
    address. Returns how many were sent; a failure is logged."""
    organiser = f"{user.full_name}, {firm_name()}" if user else firm_name()
    text = calendar_text_for(event, guests, method, organiser)
    sender = formataddr((organiser, parseaddr(settings.DEFAULT_FROM_EMAIL)[1]))
    lines = [intro, "", event.description or "Untitled", when(event)]
    if event.location:
        lines.append(event.location)
    lines += ["", f"{organiser}"]
    sent = 0
    for guest in guests:
        message = EmailMultiAlternatives(
            subject,
            "\n".join(lines),
            sender,
            [guest.email],
            reply_to=[calendar_address()],
        )
        message.attach_alternative(text, f"text/calendar; method={method}")
        message.attach("invite.ics", text, "application/ics")
        try:
            message.send(fail_silently=False)
            sent += 1
        except Exception:
            logger.exception("Could not send the invitation to %s", guest.email)
    return sent


def send_invitation(event, guests, user):
    """Invite the guests (the full guest list goes in the calendar text,
    so each sees who else is asked)."""
    _ensure_uid(event)
    name = user.full_name if user else firm_name()
    return _send(
        event,
        guests,
        "REQUEST",
        f"Invitation: {event.description or 'Untitled'}",
        f"{name} has invited you to:",
        user,
    )


def send_update(event, user):
    """The event changed: raise the revision, forget the answers, and send
    it to every guest again. Returns how many were sent."""
    guests = list(event.guests.all())
    if not guests:
        return 0
    _ensure_uid(event)
    event.invite_sequence += 1
    event.save(update_fields=["invite_sequence"])
    event.guests.update(status="needs-action", responded_at=None)
    for guest in guests:
        guest.status = "needs-action"
    name = user.full_name if user else firm_name()
    return _send(
        event,
        guests,
        "REQUEST",
        f"Updated invitation: {event.description or 'Untitled'}",
        f"{name} has changed this event:",
        user,
    )


def send_cancellation(event, guests, user):
    """Tell the guests the event is off, or that they are no longer asked
    to it."""
    if not guests or not event.invite_uid or not can_invite():
        return 0
    event.invite_sequence += 1
    event.save(update_fields=["invite_sequence"])
    name = user.full_name if user else firm_name()
    return _send(
        event,
        guests,
        "CANCEL",
        f"Cancelled: {event.description or 'Untitled'}",
        f"{name} has cancelled this event:",
        user,
    )


def after_change(event, before, user):
    """After an event is saved: if what its guests were told has changed,
    send the invitation again."""
    if can_invite() and before != details(event) and event.guests.exists():
        send_update(event, user)


# --- a guest's answer -------------------------------------------------------


@dataclass
class Reply:
    uid: str
    email: str
    status: str
    sequence: int


def read_reply(text):
    """A guest's answer in iCalendar text (METHOD:REPLY, with the guest as
    the attendee and their answer as its PARTSTAT), or None for text that
    is not one."""
    calendar = Calendar.from_ical(text)
    if str(calendar.get("METHOD", "")).upper() != "REPLY":
        return None
    for vevent in calendar.walk("VEVENT"):
        attendees = vevent.get("ATTENDEE")
        if attendees is None:
            continue
        if not isinstance(attendees, list):
            attendees = [attendees]
        for attendee in attendees:
            return Reply(
                uid=str(vevent.get("UID", "")).strip(),
                email=str(attendee).lower().removeprefix("mailto:"),
                status=str(attendee.params.get("PARTSTAT", "NEEDS-ACTION")).lower(),
                sequence=int(vevent.get("SEQUENCE", 0) or 0),
            )
    return None


def record_reply(reply):
    """Put a guest's answer on the guest. Returns (outcome, guest):
    'answered' with the guest; 'missing' when the event is not here,
    'unknown' when the address is not a guest of it, 'stale' for an
    answer to an older revision than the one sent."""
    event = None
    if reply.uid:
        event = Event.objects.filter(invite_uid=reply.uid).first()
    if event is None:
        return "missing", None
    guest = event.guests.filter(email__iexact=reply.email).first()
    if guest is None:
        return "unknown", None
    if reply.sequence < event.invite_sequence:
        return "stale", guest
    guest.status = reply.status if reply.status in ANSWERS else "needs-action"
    guest.responded_at = timezone.now()
    guest.save(update_fields=["status", "responded_at"])
    return "answered", guest


def answer_words(guest):
    return {
        "accepted": "accepted",
        "declined": "declined",
        "tentative": "replied maybe to",
    }.get(guest.status, "has not answered")


# --- telling the user -------------------------------------------------------


def notify(user, subject, body):
    """A short note to a user about an invitation. A failure to send is
    logged; the webhook's answer does not depend on it."""
    if user is None or not user.email:
        return
    try:
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Could not send the invitation note to %s", user.email)


def describe(event):
    text = event.date.strftime("%a, %b %-d")
    if event.end_date:
        text += event.end_date.strftime(" to %a, %b %-d")
    if event.start_time:
        text += " at " + event.start_time.strftime("%-I:%M %p")
    return f"{event.description} on {text}"


# --- the webhook --------------------------------------------------------------

AUTH_WORDS = ("spf", "dkim", "dmarc", "authentication")


def authentication(post):
    """What Mailgun says of the message's SPF, DKIM and DMARC, wherever in
    the post it puts it: its own fields, or the message's headers. Logged
    for now, to learn the payload before a sender check relies on it."""
    found = {
        key: value
        for key, value in post.items()
        if any(word in key.lower() for word in AUTH_WORDS)
    }
    try:
        headers = json.loads(post.get("message-headers") or "[]")
    except ValueError:
        headers = []
    for header in headers:
        if (
            isinstance(header, list)
            and len(header) == 2
            and any(word in str(header[0]).lower() for word in AUTH_WORDS)
            and not str(header[0]).lower().startswith("dkim-signature")
        ):
            found[header[0]] = header[1]
    return found


NOTES = {
    "created": ("Calendar: invitation posted", "Posted to the firm's calendar: {}."),
    "updated": ("Calendar: invitation updated", "Updated: {}."),
    "cancelled": ("Calendar: invitation cancelled", "Removed: {}."),
    "stale": (
        "Calendar: invitation not posted",
        "An older version of an invitation already posted arrived, so it "
        "was left as it is: {}.",
    ),
}


def receive(post, files):
    """A message sent to the calendar address (the webhook has checked its
    signature). A guest's answer to one of the firm's invitations is
    recorded on the guest, whoever sent it; anything else must come from
    an active firm user and carry an invitation, which is posted as a firm
    event. The sender hears what happened. Returns the outcome, for the
    log."""
    logger.info("Calendar address message authentication: %s", authentication(post))
    text = calendar_text(post, files)
    reply = None
    if text is not None:
        try:
            reply = read_reply(text)
        except Exception:
            reply = None
    if reply is not None:
        outcome, guest = record_reply(reply)
        if outcome == "answered":
            who = guest.name or guest.email
            words = answer_words(guest)
            notify(
                guest.invited_by,
                f"Calendar: {who} {words} your invitation",
                f"{who} {words} {describe(guest.event)}.",
            )
        return f"reply {outcome}"

    sender = parseaddr(post.get("from") or post.get("sender") or "")[1]
    user = CustomUser.objects.filter(email__iexact=sender, is_active=True).first()
    if user is None:
        return "sender unknown"

    subject = post.get("subject", "").strip() or "(no subject)"
    invitation = None
    if text is not None:
        try:
            invitation = parse_invitation(text)
        except Exception:
            logger.exception("A forwarded invitation could not be read")
    if invitation is None:
        notify(
            user,
            "Calendar: invitation not posted",
            f'The message "{subject}" had no calendar invitation attached, '
            "so nothing was posted. Forward the invitation itself, with its "
            "attachment, rather than a copy of its text.",
        )
        return "no invitation"

    outcome, event = post_invitation(user, invitation)
    if outcome in NOTES:
        note_subject, note = NOTES[outcome]
        notify(user, note_subject, note.format(describe(event)))
    return outcome
