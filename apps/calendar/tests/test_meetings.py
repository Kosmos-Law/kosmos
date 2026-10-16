"""Virtual meetings: an invitation's join link, details and organizer are
kept on the event, sent out again in the firm's own invitations, and
carried to and from Google; the links typed into locations before there
was a field for them are moved into it."""

import importlib
from datetime import date, time

import pytest
from django.apps import apps as django_apps
from django.urls import reverse

import apps.calendar.google as google
import apps.calendar.sync as sync
from apps.calendar import invitations, meetings
from apps.calendar.models import Event, EventGuest

from .test_invitations import ics

pytestmark = pytest.mark.django_db

DAY = {"start": {"date": "2030-03-04"}, "end": {"date": "2030-03-05"}}
TIMES = "DTSTART:20300304T140000Z\r\nDTEND:20300304T150000Z\r\nSUMMARY:Meet and confer"

ZOOM_LINK = "https://us02web.zoom.us/j/81234567890?pwd=AbC123xyz"
TEAMS_LINK = (
    "https://teams.microsoft.com/l/meetup-join/19%3ameeting_NjQ5%40thread.v2/0"
    "?context=%7b%22Tid%22%3a%22abc%22%7d"
)
MEET_LINK = "https://meet.google.com/abc-defg-hij"


# --- finding the link --------------------------------------------------------


def test_a_link_run_on_into_its_labels_ends_at_them():
    text = f"Join Zoom Meeting{ZOOM_LINK}Meeting ID: 812 3456 7890Passcode: 1234"
    assert meetings.find_meeting_url(text) == ZOOM_LINK


def test_a_teams_link_in_angle_brackets():
    text = f"Microsoft Teams meeting\nClick here to join <{TEAMS_LINK}>\nMeeting ID: 1"
    assert meetings.find_meeting_url(text) == TEAMS_LINK


def test_only_a_meeting_services_link_is_a_meeting_link():
    assert meetings.find_meeting_url("Map: https://maps.example.com/court") == ""
    assert meetings.meeting_type(ZOOM_LINK) == "Zoom"
    assert meetings.meeting_type(MEET_LINK) == "Virtual"
    assert meetings.meeting_type("https://notzoom.us.example.com/j/1") is None


def test_googles_html_text_is_read_as_plain_text():
    assert meetings.plain_text("Line one<br>Line &amp; two<p>x</p>") == (
        "Line one\nLine & two\nx"
    )


# --- forwarded in ------------------------------------------------------------


def test_a_zoom_invitation_keeps_its_link_and_its_text():
    invitation = invitations.parse_invitation(
        ics(
            f"{TIMES}\r\nLOCATION:{ZOOM_LINK}\r\n"
            "DESCRIPTION:Meeting ID: 812 3456 7890\\nPasscode: 1234"
        )
    )

    assert invitation.meeting_url == ZOOM_LINK
    assert invitation.location == ""
    assert invitation.details == "Meeting ID: 812 3456 7890\nPasscode: 1234"
    assert (invitation.organizer_name, invitation.organizer_email) == (
        "Opposing",
        "oc@example.org",
    )


def test_a_teams_invitation_takes_its_link_from_its_own_property():
    invitation = invitations.parse_invitation(
        ics(
            f"{TIMES}\r\nLOCATION:Microsoft Teams Meeting\r\n"
            f"X-MICROSOFT-SKYPETEAMSMEETINGURL:{TEAMS_LINK}\r\n"
            "DESCRIPTION:Join on your computer"
        )
    )

    assert invitation.meeting_url == TEAMS_LINK
    assert invitation.location == ""


def test_a_meet_invitation_takes_its_conference_link():
    invitation = invitations.parse_invitation(
        ics(
            f"{TIMES}\r\nLOCATION:Room 4\r\n"
            "CONFERENCE;VALUE=URI;FEATURE=PHONE:tel:+1-555-0100\r\n"
            f"CONFERENCE;VALUE=URI;FEATURE=VIDEO:{MEET_LINK}"
        )
    )

    assert invitation.meeting_url == MEET_LINK
    assert invitation.location == "Room 4"


def test_googles_own_property_is_read_too():
    invitation = invitations.parse_invitation(
        ics(f"{TIMES}\r\nX-GOOGLE-CONFERENCE:{MEET_LINK}")
    )
    assert invitation.meeting_url == MEET_LINK


def test_a_posted_invitation_is_a_zoom_event_with_its_organizer(user):
    invitation = invitations.parse_invitation(
        ics(f"{TIMES}\r\nLOCATION:{ZOOM_LINK}\r\nDESCRIPTION:Passcode: 1234")
    )

    outcome, event = invitations.post_invitation(user, invitation)

    event.refresh_from_db()
    assert outcome == "created"
    assert event.meeting_url == ZOOM_LINK
    assert event.event_type == "Zoom"
    assert event.details == "Passcode: 1234"
    assert event.location is None
    assert event.organizer_email == "oc@example.org"


# --- sent out ----------------------------------------------------------------


@pytest.fixture
def meeting(user):
    return Event.objects.create(
        user=user,
        description="Mediation",
        date=date(2030, 3, 4),
        start_time=time(9),
        end_time=time(10),
        status="Pending",
        meeting_url=ZOOM_LINK,
        details="Passcode: 1234",
    )


def test_the_firms_invitation_carries_the_link_and_the_text(meeting):
    meeting.invite_uid = "x@kosmos"
    guest = EventGuest(event=meeting, email="ann@example.org")

    text = invitations.calendar_text_for(meeting, [guest], "REQUEST", "Firm")
    unfolded = text.replace("\r\n ", "")

    assert f"LOCATION:{ZOOM_LINK}" in unfolded
    assert f"URL:{ZOOM_LINK}" in unfolded
    assert f"CONFERENCE;FEATURE=VIDEO;LABEL=Join;VALUE=URI:{ZOOM_LINK}" in unfolded
    assert f"DESCRIPTION:Join: {ZOOM_LINK}\\n\\nPasscode: 1234" in unfolded
    # and reads back as the same meeting
    read = invitations.parse_invitation(text)
    assert read.meeting_url == ZOOM_LINK
    assert read.location == ""


def test_the_email_gives_the_link_and_the_text(meeting, user, settings, mailoutbox):
    settings.CALENDAR_INBOUND_ADDRESS = "calendar@mail.example.com"
    guest = EventGuest.objects.create(event=meeting, email="ann@example.org")

    assert invitations.send_invitation(meeting, [guest], user) == 1

    body = mailoutbox[-1].body
    assert f"Join: {ZOOM_LINK}\n\nPasscode: 1234" in body
    assert "BEGIN:VCALENDAR" in mailoutbox[-1].alternatives[0][0]


def test_a_new_link_or_text_is_a_change_the_guests_hear_of(meeting):
    before = invitations.details(meeting)
    meeting.details = "Passcode: 9999"
    assert invitations.details(meeting) != before


# --- Google ------------------------------------------------------------------


class FakeGoogle:
    def __init__(self):
        self.sent = []

    def events(self):
        return self

    def insert(self, calendarId, body):
        self.sent.append(body)
        return self

    def update(self, calendarId, eventId, body):
        self.sent.append(body)
        return self

    def execute(self):
        return {"id": "google-1"}


@pytest.fixture
def remote(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(google, "check_credentials", lambda: True)
    monkeypatch.setattr(google, "build_service", lambda: fake)
    return fake


def test_google_gets_the_link_as_the_location_and_atop_the_text(meeting, remote):
    assert sync.push_event(meeting) == "ok"

    body = remote.sent[-1]
    assert body["location"] == ZOOM_LINK
    assert body["description"] == f"Join: {ZOOM_LINK}\n\nPasscode: 1234"


def test_a_place_stays_googles_location(meeting, remote):
    meeting.location = "Courtroom 4"
    meeting.save()
    sync.push_event(meeting)

    assert remote.sent[-1]["location"] == "Courtroom 4"


def test_what_kosmos_sent_comes_back_as_it_was():
    data = google._parse_google_event(
        DAY
        | {
            "location": ZOOM_LINK,
            "description": f"Join: {ZOOM_LINK}\n\nPasscode: 1234",
        }
    )

    assert data["meeting_url"] == ZOOM_LINK
    assert data["location"] is None
    assert data["details"] == "Passcode: 1234"


def test_a_meet_added_on_google_is_the_events_link():
    data = google._parse_google_event(
        DAY
        | {
            "hangoutLink": MEET_LINK,
            "conferenceData": {
                "entryPoints": [
                    {"entryPointType": "phone", "uri": "tel:+1-555-0100"},
                    {"entryPointType": "video", "uri": MEET_LINK},
                ]
            },
            "description": "Agenda<br>Item one",
        }
    )

    assert data["meeting_url"] == MEET_LINK
    assert data["details"] == "Agenda\nItem one"


def test_a_link_removed_on_google_is_removed_here():
    data = google._parse_google_event(DAY | {"location": "Courtroom 4"})

    assert data["meeting_url"] == ""
    assert data["details"] == ""
    assert data["location"] == "Courtroom 4"


# --- the move ----------------------------------------------------------------


def test_links_typed_into_locations_are_moved():
    glued = Event.objects.create(
        date=date(2030, 3, 4),
        description="Hearing",
        location=f"Join Zoom Meeting{ZOOM_LINK}Meeting ID: 812 3456 7890Passcode: 1234",
    )
    bare = Event.objects.create(
        date=date(2030, 3, 4), description="Call", location=MEET_LINK
    )
    place = Event.objects.create(
        date=date(2030, 3, 4), description="Trial", location="Courtroom 4"
    )

    move = importlib.import_module("apps.calendar.migrations.0011_move_meeting_links")
    move.move_links(django_apps, None)

    for event in (glued, bare, place):
        event.refresh_from_db()
    assert glued.meeting_url == ZOOM_LINK
    assert (
        glued.details == "Join Zoom Meeting\nMeeting ID: 812 3456 7890\nPasscode: 1234"
    )
    assert glued.location is None
    assert glued.event_type == "Zoom"
    assert (bare.meeting_url, bare.location, bare.details) == (MEET_LINK, None, "")
    assert (place.meeting_url, place.location) == ("", "Courtroom 4")


# --- the form ----------------------------------------------------------------


def test_the_form_saves_the_link_and_the_details(client, meeting):
    client.post(
        reverse("calendar:edit", args=[meeting.id]),
        {
            "description": "Mediation",
            "date": "2030-03-04",
            "start_time": "09:00",
            "end_time": "10:00",
            "status": "Pending",
            "meeting_url": MEET_LINK,
            "details": "Dial in: +1 555 0100",
        },
        HTTP_HX_REQUEST="true",
    )

    meeting.refresh_from_db()
    assert meeting.meeting_url == MEET_LINK
    assert meeting.details == "Dial in: +1 555 0100"


def test_the_event_shows_its_organizer_and_a_join_button(client, meeting):
    meeting.organizer_name = "Opposing Counsel"
    meeting.organizer_email = "oc@example.org"
    meeting.save()

    page = client.get(
        reverse("calendar:edit", args=[meeting.id]), HTTP_HX_REQUEST="true"
    ).content.decode()

    assert "Organizer: Opposing Counsel (oc@example.org)" in " ".join(page.split())
    assert f'href="{ZOOM_LINK}"' in page
    assert ">Join</a>" in page
