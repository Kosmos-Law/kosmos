"""Calendar invitations: one forwarded to the firm's calendar address is
posted as a firm event (updated by revision, removed by cancellation),
and an event's guests outside the firm are emailed invitations whose
answers come back to the same address."""

import hashlib
import hmac
import time as clock
from datetime import date, time

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.calendar import invitations
from apps.calendar.models import Event, EventGuest
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db

KEY = "signing-key"
ADDRESS = "kosmos-calendar@mail.example.com"


@pytest.fixture(autouse=True)
def inbound(settings):
    settings.CALENDAR_INBOUND_ADDRESS = ADDRESS
    settings.MAILGUN_WEBHOOK_SIGNING_KEY = KEY
    settings.INTAKE_INBOUND_RECIPIENT = "kosmos-intakes"


def ics(body, method="REQUEST", uid="abc123@google.com"):
    return (
        "BEGIN:VCALENDAR\r\nPRODID:-//Google Inc//Google Calendar//EN\r\n"
        f"VERSION:2.0\r\nMETHOD:{method}\r\nBEGIN:VEVENT\r\n{body}\r\n"
        "DTSTAMP:20260101T000000Z\r\nORGANIZER;CN=Opposing:mailto:oc@example.org\r\n"
        f"UID:{uid}\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    )


TIMED = ics(
    "DTSTART:20300304T140000Z\r\nDTEND:20300304T150000Z\r\nSEQUENCE:0\r\n"
    "STATUS:CONFIRMED\r\nSUMMARY:Deposition of J. Smith\r\nLOCATION:123 Main St"
)


def _signed(**fields):
    timestamp, token = str(int(clock.time())), "tok"
    signature = hmac.new(
        KEY.encode(), f"{timestamp}{token}".encode(), hashlib.sha256
    ).hexdigest()
    return {
        "timestamp": timestamp,
        "token": token,
        "signature": signature,
        "recipient": ADDRESS,
        "from": "Ollie <testuser@example.com>",
        "subject": "Fwd: Invitation: Deposition",
    } | fields


def _attachment(text=TIMED):
    return SimpleUploadedFile("invite.ics", text.encode(), content_type="text/calendar")


def _post(client, data):
    return client.post(reverse("intakes:api-inbound-email"), data)


# --- reading -----------------------------------------------------------------


def test_a_timed_invitation_is_read_in_the_firms_time():
    invitation = invitations.parse_invitation(TIMED)

    assert invitation.uid == "abc123@google.com"
    assert invitation.summary == "Deposition of J. Smith"
    assert invitation.location == "123 Main St"
    # 14:00Z on a March day before the clocks change is 9:00 AM Eastern
    assert invitation.date == date(2030, 3, 4)
    assert (invitation.start_time, invitation.end_time) == (time(9), time(10))
    assert invitation.end_date is None


def test_an_all_day_span_keeps_its_last_day():
    invitation = invitations.parse_invitation(
        ics("DTSTART;VALUE=DATE:20300304\r\nDTEND;VALUE=DATE:20300307\r\nSUMMARY:Trial")
    )

    assert invitation.date == date(2030, 3, 4)
    assert invitation.end_date == date(2030, 3, 6)
    assert invitation.start_time is None


# --- forwarded in -------------------------------------------------------------


def test_a_forwarded_invitation_becomes_a_firm_event(client, user, mailoutbox):
    response = _post(client, _signed(**{"attachment-1": _attachment()}))

    assert response.status_code == 200
    event = Event.objects.get(ical_uid="abc123@google.com")
    assert event.description == "Deposition of J. Smith"
    assert event.status == "Pending"
    assert event.user == user
    assert not event.assignees.exists()  # the firm's
    assert event.matter is None
    assert mailoutbox[-1].to == ["testuser@example.com"]
    assert mailoutbox[-1].subject == "Calendar: invitation posted"
    assert "Deposition of J. Smith on Mon, Mar 4 at 9:00 AM" in mailoutbox[-1].body


def test_a_later_revision_updates_it_and_a_cancellation_removes_it(client, user):
    _post(client, _signed(**{"attachment-1": _attachment()}))
    moved = ics(
        "DTSTART:20300305T140000Z\r\nDTEND:20300305T160000Z\r\nSEQUENCE:1\r\n"
        "SUMMARY:Deposition of J. Smith"
    )
    _post(client, _signed(**{"attachment-1": _attachment(moved)}))

    event = Event.objects.get(ical_uid="abc123@google.com")
    assert (event.date, event.end_time) == (date(2030, 3, 5), time(11))

    cancel = ics(
        "DTSTART:20300305T140000Z\r\nSEQUENCE:2\r\nSTATUS:CANCELLED\r\nSUMMARY:x",
        method="CANCEL",
    )
    _post(client, _signed(**{"attachment-1": _attachment(cancel)}))
    assert not Event.objects.filter(ical_uid="abc123@google.com").exists()


def test_a_stranger_cannot_post_to_the_calendar(client, user, mailoutbox):
    response = _post(
        client,
        _signed(**{"attachment-1": _attachment(), "from": "spam@example.net"}),
    )

    assert response.status_code == 200
    assert not Event.objects.exists()
    assert mailoutbox == []


def test_an_unsigned_post_is_refused(client, user):
    data = _signed(**{"attachment-1": _attachment()}) | {"signature": "nope"}

    assert _post(client, data).status_code == 403
    assert not Event.objects.exists()


def test_a_message_without_an_invitation_says_so(client, user, mailoutbox):
    _post(client, _signed(**{"body-plain": "See you there"}))

    assert not Event.objects.exists()
    assert mailoutbox[-1].subject == "Calendar: invitation not posted"


def test_with_no_calendar_address_the_mail_is_not_the_calendars(client, user, settings):
    settings.CALENDAR_INBOUND_ADDRESS = ""
    _post(client, _signed(**{"attachment-1": _attachment()}))

    assert not Event.objects.exists()


# --- guests -----------------------------------------------------------------


@pytest.fixture
def firm_event(user):
    return Event.objects.create(
        user=user,
        description="Mediation",
        date=date(2030, 3, 4),
        start_time=time(9),
        end_time=time(10),
        status="Pending",
    )


def _invite(client, event, email, name=""):
    return client.post(
        reverse("calendar:guest-add", args=[event.id]),
        {"email": email, "name": name},
        HTTP_HX_REQUEST="true",
    )


def test_a_guest_is_emailed_an_invitation(client, user, firm_event, mailoutbox):
    response = _invite(client, firm_event, "Ann@Example.org", "Ann Lee")

    assert response.status_code == 200
    guest = EventGuest.objects.get(event=firm_event)
    assert (guest.email, guest.name, guest.invited_by) == (
        "ann@example.org",
        "Ann Lee",
        user,
    )
    message = mailoutbox[-1]
    assert message.to == ["ann@example.org"]
    assert message.reply_to == [ADDRESS]
    assert message.subject == "Invitation: Mediation"
    text = message.alternatives[0][0]
    assert "METHOD:REQUEST" in text
    assert f"mailto:{ADDRESS}" in text
    assert "mailto:ann@example.org" in text


def test_someone_in_the_firm_is_pointed_to_the_assignees(
    client, user, firm_event, mailoutbox
):
    CustomUser.objects.create(
        username="pat", first_name="Pat", last_name="Doe", email="pat@example.com"
    )
    response = _invite(client, firm_event, "PAT@example.com")

    assert b"Pat Doe is in the firm. Add them as an assignee instead" in (
        response.content
    )
    assert not EventGuest.objects.exists()
    assert mailoutbox == []


def test_an_address_on_the_firms_own_domain_is_refused(client, firm_event):
    Firm.objects.create(name="Craig Legal", email="office@craiglegal.law")

    response = _invite(client, firm_event, "front.desk@craiglegal.law")

    assert b"is in the firm" in response.content
    assert not EventGuest.objects.exists()


def test_a_public_mail_domain_is_not_the_firms(client, firm_event):
    Firm.objects.create(name="Solo", email="solo.lawyer@gmail.com")

    _invite(client, firm_event, "client@gmail.com")

    assert EventGuest.objects.filter(email="client@gmail.com").exists()


def test_without_a_calendar_address_there_is_no_inviting(
    client, firm_event, settings, mailoutbox
):
    settings.CALENDAR_INBOUND_ADDRESS = ""
    response = _invite(client, firm_event, "ann@example.org")

    assert b"Inviting guests is not set up" in response.content
    assert not EventGuest.objects.exists()


def test_a_change_goes_out_again_and_a_delete_cancels(
    client, user, firm_event, mailoutbox
):
    _invite(client, firm_event, "ann@example.org")
    client.post(
        reverse("calendar:edit", args=[firm_event.id]),
        {
            "description": "Mediation",
            "date": "2030-03-05",
            "start_time": "09:00",
            "end_time": "10:00",
            "status": "Pending",
        },
        HTTP_HX_REQUEST="true",
    )
    assert mailoutbox[-1].subject == "Updated invitation: Mediation"
    assert "SEQUENCE:1" in mailoutbox[-1].alternatives[0][0]

    client.delete(
        reverse("calendar:delete", args=[firm_event.id]), HTTP_HX_REQUEST="true"
    )
    assert mailoutbox[-1].subject == "Cancelled: Mediation"
    assert "METHOD:CANCEL" in mailoutbox[-1].alternatives[0][0]


def test_a_guests_answer_is_recorded_and_the_inviter_told(
    client, user, firm_event, mailoutbox
):
    _invite(client, firm_event, "ann@example.org", "Ann Lee")
    firm_event.refresh_from_db()
    reply = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nMETHOD:REPLY\r\nBEGIN:VEVENT\r\n"
        f"UID:{firm_event.invite_uid}\r\nSEQUENCE:0\r\n"
        "DTSTAMP:20260101T000000Z\r\n"
        "ATTENDEE;PARTSTAT=ACCEPTED:mailto:ann@example.org\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    # the answer comes from the guest, not from a firm user
    _post(
        client,
        _signed(**{"attachment-1": _attachment(reply), "from": "ann@example.org"}),
    )

    guest = EventGuest.objects.get(event=firm_event)
    assert guest.status == "accepted"
    assert mailoutbox[-1].to == ["testuser@example.com"]
    assert mailoutbox[-1].subject == "Calendar: Ann Lee accepted your invitation"
