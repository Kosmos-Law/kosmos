"""What a pull from Google writes into an event besides its date and matter:
a title too long for the description column is cut to fit, and a location
removed on Google is removed here."""

from datetime import date

import pytest

import apps.calendar.google as google
from apps.calendar.models import Event

pytestmark = pytest.mark.django_db

DAY = {"start": {"date": "2030-03-04"}, "end": {"date": "2030-03-05"}}
LIMIT = Event._meta.get_field("description").max_length


def _in_step(**fields):
    """An event Kosmos holds that matches what Google has."""
    event = Event.objects.create(
        date=date(2030, 3, 4),
        description="Hearing",
        status="Pending",
        google_id="google-1",
        **fields,
    )
    Event.objects.filter(pk=event.pk).update(google_synced_at=event.updated_at)
    event.refresh_from_db()
    return event


def _pull(**google_fields):
    return google._process_google_event({"id": "google-1"} | DAY | google_fields)


# --- long titles -----------------------------------------------------------


def test_long_title_is_cut_on_a_word_boundary():
    title = " ".join(["deposition"] * 40)
    assert len(title) > LIMIT

    assert _pull(summary=title) == "created"

    description = Event.objects.get(google_id="google-1").description
    assert len(description) <= LIMIT
    assert title.startswith(description)
    assert description.endswith("deposition")


def test_long_title_with_no_spaces_is_cut_at_the_limit():
    _pull(summary="x" * 400)

    assert Event.objects.get(google_id="google-1").description == "x" * LIMIT


def test_title_that_fits_is_kept_whole():
    title = "y" * LIMIT

    _pull(summary=title)

    assert Event.objects.get(google_id="google-1").description == title


def test_long_title_on_an_event_already_held_is_cut_too():
    event = _in_step()
    title = " ".join(["continued"] * 40)

    assert _pull(summary=title) == "updated"

    event.refresh_from_db()
    assert len(event.description) <= LIMIT
    assert event.description.endswith("continued")


# --- location --------------------------------------------------------------


def test_location_removed_on_google_is_cleared():
    event = _in_step(location="Courtroom 4, 100 Main St")

    _pull(summary="Hearing")

    event.refresh_from_db()
    assert event.location is None


def test_location_still_on_google_is_kept():
    event = _in_step(location="Courtroom 4, 100 Main St")

    _pull(summary="Hearing", location="Courtroom 4, 100 Main St")

    event.refresh_from_db()
    assert event.location == "Courtroom 4, 100 Main St"


def test_location_is_not_cleared_under_unpushed_local_edits():
    event = _in_step()
    event.location = "Courtroom 4, 100 Main St"
    event.save()

    assert _pull(summary="Hearing") == "skipped"

    event.refresh_from_db()
    assert event.location == "Courtroom 4, 100 Main St"


def test_removing_the_location_leaves_the_meeting_type():
    event = _in_step(event_type="Zoom", location="https://zoom.example/j/1")

    _pull(summary="Hearing")

    event.refresh_from_db()
    assert event.location is None
    assert event.event_type == "Zoom"
