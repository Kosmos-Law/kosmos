"""Event titles on Google, out and back.

Kosmos writes "Matter - Description" (the description alone for an event on
no matter). Reading its own title back must not re-derive the matter from
text: that moved events to any matter whose name contained the text and cut
matter names holding " - " in two. A title is read only when it was changed
on Google, and then a matter is matched by its whole name or not at all.
"""

from datetime import date

import pytest

import apps.calendar.google as google
import apps.calendar.sync as sync
from apps.calendar.models import Event
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db

DAY = {"start": {"date": "2030-03-04"}, "end": {"date": "2030-03-05"}}


class FakeGoogle:
    """Stands in for the Calendar API client; keeps what was sent."""

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


def _matter(practice_area, name, status="Open"):
    return Matter.objects.create(name=name, status=status, practice_area=practice_area)


def _event(matter, description="Hearing", **extra):
    return Event.objects.create(
        matter=matter,
        date=date(2030, 3, 4),
        description=description,
        status="Pending",
        **extra,
    )


def _pushed(matter, remote, description="Hearing"):
    """An event pushed to Google, with the title Google now holds."""
    event = _event(matter, description)
    assert sync.push_event(event) == "ok"
    return event, remote.sent[-1]["summary"]


def _pull(event, title):
    result = google._process_google_event(
        {"id": event.google_id, "summary": title} | DAY
    )
    event.refresh_from_db()
    return result


# --- the title Kosmos writes -----------------------------------------------


def test_title_is_matter_then_description(remote, matter):
    _, title = _pushed(matter, remote)

    assert title == "Sample Test Matter - Hearing"


def test_title_of_an_event_on_no_matter_is_its_description(remote):
    event, title = _pushed(None, remote)

    assert title == "Hearing"

    event.description = "Hearing moved"
    event.save()
    sync.push_event(event)
    assert remote.sent[-1]["summary"] == "Hearing moved"


# --- reading its own title back --------------------------------------------


def test_round_trip_keeps_the_matter_when_another_name_contains_it(
    remote, practice_area
):
    # Made first so the old contains-match, which took the first hit, found it.
    longer = _matter(practice_area, "Smith v. Jones")
    smith = _matter(practice_area, "Smith")
    event, title = _pushed(smith, remote)

    assert _pull(event, title) == "updated"

    assert event.matter == smith != longer
    assert event.description == "Hearing"


def test_round_trip_keeps_a_matter_name_holding_a_dash(remote, practice_area):
    estate = _matter(practice_area, "Estate - Doe")
    _matter(practice_area, "Estate")
    event, title = _pushed(estate, remote)

    _pull(event, title)

    assert event.matter == estate
    assert event.description == "Hearing"


def test_round_trip_keeps_an_event_on_no_matter(remote, practice_area):
    _matter(practice_area, "Call")
    event, title = _pushed(None, remote, description="Call - opposing counsel")

    _pull(event, title)

    assert event.matter is None
    assert event.description == "Call - opposing counsel"


def test_round_trip_still_takes_the_new_date(remote, matter):
    event, title = _pushed(matter, remote)

    google._process_google_event(
        {
            "id": event.google_id,
            "summary": title,
            "start": {"date": "2030-04-01"},
            "end": {"date": "2030-04-02"},
        }
    )

    event.refresh_from_db()
    assert str(event.date) == "2030-04-01"
    assert event.matter == matter


def test_old_none_prefix_is_not_read_as_a_change(remote, practice_area):
    """Events on no matter used to be pushed as "None - description"."""
    _matter(practice_area, "Nonesuch Holdings")
    event, _ = _pushed(None, remote)

    _pull(event, "None - Hearing")

    assert event.matter is None
    assert event.description == "Hearing"


def test_renamed_matter_is_not_read_as_a_change(remote, matter):
    event, title = _pushed(matter, remote)
    Matter.objects.filter(pk=matter.pk).update(name="Renamed Matter")

    _pull(event, title)

    assert event.matter == matter
    assert event.description == "Hearing"


# --- a title changed on Google ---------------------------------------------


def test_edited_description_keeps_the_matter(remote, practice_area):
    estate = _matter(practice_area, "Estate - Doe")
    event, _ = _pushed(estate, remote)

    _pull(event, "Estate - Doe - Hearing continued")

    assert event.matter == estate
    assert event.description == "Hearing continued"


def test_title_naming_another_matter_exactly_moves_the_event(
    remote, matter, practice_area
):
    other = _matter(practice_area, "Brown v. Board")
    event, _ = _pushed(matter, remote)

    _pull(event, "brown v. board - Hearing")

    assert event.matter == other
    assert event.description == "Hearing"


def test_title_naming_part_of_a_matter_name_moves_nothing(
    remote, matter, practice_area
):
    _matter(practice_area, "Brown v. Board")
    event, _ = _pushed(matter, remote)

    _pull(event, "Brown - Status conference")

    assert event.matter == matter
    assert event.description == "Brown - Status conference"


def test_title_with_no_matter_keeps_the_matter_and_all_its_text(remote, matter):
    event, _ = _pushed(matter, remote)

    _pull(event, "Call the clerk")

    assert event.matter == matter
    assert event.description == "Call the clerk"


def test_two_matters_of_one_name_prefer_the_open_one(remote, matter, practice_area):
    _matter(practice_area, "Twin", status="Closed")
    open_twin = _matter(practice_area, "Twin")
    event, _ = _pushed(matter, remote)

    _pull(event, "Twin - Hearing")

    assert event.matter == open_twin


def test_two_open_matters_of_one_name_move_nothing(remote, matter, practice_area):
    _matter(practice_area, "Twin")
    _matter(practice_area, "Twin")
    event, _ = _pushed(matter, remote)

    _pull(event, "Twin - Status conference")

    assert event.matter == matter
    assert event.description == "Twin - Status conference"


def test_unpushed_local_edit_is_left_alone(remote, matter):
    event, _ = _pushed(matter, remote)
    event.description = "Edited here"
    event.save()

    assert _pull(event, "Sample Test Matter - Edited on Google") == "skipped"
    assert event.description == "Edited here"


# --- an event made on Google -----------------------------------------------


def test_event_made_on_google_arrives_pending(practice_area):
    result = google._process_google_event(
        {"id": "made-on-google", "summary": "Lunch with the clerk"} | DAY
    )

    event = Event.objects.get(google_id="made-on-google")
    assert result == "created"
    assert event.status == "Pending"
    assert event.matter is None
    assert event.description == "Lunch with the clerk"


def test_event_made_on_google_takes_a_matter_named_exactly(matter, practice_area):
    _matter(practice_area, "Sample Test Matter Two")

    google._process_google_event(
        {"id": "made-on-google", "summary": "Sample Test Matter - Deposition"} | DAY
    )

    event = Event.objects.get(google_id="made-on-google")
    assert event.matter == matter
    assert event.description == "Deposition"


def test_event_made_on_google_keeps_a_title_that_names_no_matter(matter):
    google._process_google_event(
        {"id": "made-on-google", "summary": "Sample - Deposition"} | DAY
    )

    event = Event.objects.get(google_id="made-on-google")
    assert event.matter is None
    assert event.description == "Sample - Deposition"
