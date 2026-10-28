"""An event over several days: it has an end date, shows on every day it
covers, and reads in days in the lists."""

import json
from datetime import date, time, timedelta

import pytest
from django.urls import reverse

from apps.calendar.forms import EventForm
from apps.calendar.models import Event

pytestmark = pytest.mark.django_db

MARCH = {"start": "2030-03-01", "end": "2030-04-01"}


def _data(**changes):
    return {
        "date": "2030-03-04",
        "description": "Conference",
        "status": "Pending",
        "party": "Client",
    } | changes


def _event(**fields):
    """An event the feed shows: the saved filter starts on Pending."""
    fields.setdefault("status", "Pending")
    return Event.objects.create(**fields)


def _feed(client, params=MARCH):
    return {
        row["id"]: row for row in client.get(reverse("calendar:feed"), params).json()
    }


# --- the form --------------------------------------------------------------


def test_an_end_date_after_the_date_is_kept():
    form = EventForm(_data(end_date="2030-03-06"))

    assert form.is_valid(), form.errors
    assert form.cleaned_data["end_date"] == date(2030, 3, 6)


def test_an_end_date_equal_to_the_date_is_none():
    form = EventForm(_data(end_date="2030-03-04"))

    assert form.is_valid(), form.errors
    assert form.cleaned_data["end_date"] is None


def test_an_end_date_before_the_date_is_refused():
    form = EventForm(_data(end_date="2030-03-03"))

    assert not form.is_valid()
    assert form.errors["end_date"] == ["The last day must be on or after the date."]


def test_over_several_days_the_end_time_may_be_before_the_start_time():
    form = EventForm(_data(end_date="2030-03-06", start_time="14:00", end_time="10:00"))

    assert form.is_valid(), form.errors


def test_on_one_day_the_end_time_must_still_follow_the_start_time():
    form = EventForm(_data(end_date="2030-03-04", start_time="14:00", end_time="10:00"))

    assert not form.is_valid()
    assert "end_time" in form.errors


def test_the_form_saves_the_span(client):
    client.post(reverse("calendar:add"), _data(end_date="2030-03-06"))

    event = Event.objects.get(description="Conference")
    assert event.end_date == date(2030, 3, 6)
    assert event.last_date == date(2030, 3, 6)


# --- the feed --------------------------------------------------------------


def test_the_feed_ends_an_all_day_span_the_day_after_its_last(client, user):
    event = _event(
        user=user, date=date(2030, 3, 4), end_date=date(2030, 3, 6), description="Trial"
    )

    row = _feed(client)[str(event.id)]

    assert row["allDay"] is True
    assert row["start"] == "2030-03-04"
    assert row["end"] == "2030-03-07"


def test_the_feed_ends_a_timed_span_on_its_last_day(client, user):
    event = _event(
        user=user,
        date=date(2030, 3, 4),
        end_date=date(2030, 3, 5),
        start_time=time(14, 0),
        end_time=time(10, 0),
        description="Deposition",
    )

    row = _feed(client)[str(event.id)]

    assert row["allDay"] is False
    assert row["start"] == "2030-03-04T14:00:00"
    assert row["end"] == "2030-03-05T10:00:00"


def test_a_span_that_began_before_the_range_still_shows(client, user):
    event = _event(
        user=user,
        date=date(2030, 2, 27),
        end_date=date(2030, 3, 2),
        description="Trial",
    )
    before = _event(
        user=user, date=date(2030, 2, 20), end_date=date(2030, 2, 22), description="Old"
    )

    feed = _feed(client)

    assert str(event.id) in feed
    assert str(before.id) not in feed


# --- dragging --------------------------------------------------------------


def _drag(client, event, **data):
    return client.post(
        reverse("calendar:quick-update", args=[event.id]),
        json.dumps(data),
        content_type="application/json",
    )


def test_a_drag_moves_the_whole_span(client, user):
    event = _event(
        user=user, date=date(2030, 3, 4), end_date=date(2030, 3, 6), description="Trial"
    )

    response = _drag(client, event, date="2030-03-11", end_date="2030-03-13")

    assert response.status_code == 204
    event.refresh_from_db()
    assert (event.date, event.end_date) == (date(2030, 3, 11), date(2030, 3, 13))


def test_a_span_shrunk_to_one_day_loses_its_end_date(client, user):
    event = _event(
        user=user, date=date(2030, 3, 4), end_date=date(2030, 3, 6), description="Trial"
    )

    _drag(client, event, date="2030-03-04", end_date="2030-03-04")

    event.refresh_from_db()
    assert event.end_date is None


def test_an_end_date_before_the_date_is_refused_on_drag(client, user):
    event = _event(
        user=user, date=date(2030, 3, 4), end_date=date(2030, 3, 6), description="Trial"
    )

    response = _drag(client, event, date="2030-03-04", end_date="2030-03-02")

    assert response.status_code == 400
    event.refresh_from_db()
    assert event.end_date == date(2030, 3, 6)


# --- the lists -------------------------------------------------------------


def test_the_list_reads_the_span_in_days(client, user):
    _event(
        user=user,
        date=date(2030, 3, 4),
        end_date=date(2030, 3, 6),
        description="Trial week",
        status="Pending",
    )
    client.post(reverse("calendar:view-mode", args=["list"]))

    page = client.get(reverse("calendar:index")).content.decode()

    assert "to 2030-03-06" in page
    assert "3 days" in page


def test_the_models_last_day_and_moments(user):
    event = _event(
        user=user,
        date=date(2030, 3, 4),
        end_date=date(2030, 3, 5),
        start_time=time(14, 0),
        end_time=time(10, 0),
        description="Deposition",
    )

    assert event.last_date == date(2030, 3, 5)
    assert event.end_at - event.start_at == timedelta(hours=20)
