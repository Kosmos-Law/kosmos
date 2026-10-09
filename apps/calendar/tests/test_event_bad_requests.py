"""Requests the calendar's own JavaScript would never send are answered 400,
not with a server error, and change nothing."""

import json

import pytest
from django.urls import NoReverseMatch, reverse

pytestmark = pytest.mark.django_db


def _quick(client, event, body):
    return client.post(
        reverse("calendar:quick-update", args=[event.id]),
        body,
        content_type="application/json",
    )


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        "",
        json.dumps(["2030-03-05"]),
        json.dumps({"date": "March 5"}),
        json.dumps({"date": None}),
        json.dumps({"date": "2030-03-05", "start_time": "9am"}),
        json.dumps({"date": "2030-03-05", "end_time": 900}),
    ],
)
def test_unreadable_quick_update_is_refused_and_changes_nothing(client, event, body):
    response = _quick(client, event, body)

    assert response.status_code == 400
    event.refresh_from_db()
    assert str(event.date) == "2022-12-28"
    assert event.start_time is None


def test_readable_quick_update_still_moves_the_event(client, event):
    body = json.dumps(
        {"date": "2030-03-05", "start_time": "09:00:00", "end_time": "10:00:00"}
    )

    assert _quick(client, event, body).status_code == 204

    event.refresh_from_db()
    assert str(event.date) == "2030-03-05"
    assert str(event.start_time) == "09:00:00"


@pytest.mark.parametrize(
    "params",
    [
        {"start": "last week"},
        {"start": "2030-03-01", "end": "2030-13-45"},
        {"end": "soon"},
    ],
)
def test_feed_with_an_unreadable_range_is_refused(client, matter, params):
    assert client.get(reverse("calendar:feed"), params).status_code == 400
    matter_feed = reverse("calendar:feed-matter", args=[matter.id])
    assert client.get(matter_feed, params).status_code == 400


def test_feed_reads_the_ranges_the_calendar_sends(client):
    params = {"start": "2030-03-01T00:00:00-05:00", "end": "2030-04-01T00:00:00Z"}

    assert client.get(reverse("calendar:feed"), params).status_code == 200
    assert client.get(reverse("calendar:feed")).status_code == 200


def test_add_from_a_matter_has_one_address(matter):
    """ "events/add/<matter id>" never reached the view: "events/add/<origin>"
    sits above it and takes a bare number as an origin. The route that could
    not be reached is gone; the one with an origin is the address."""
    with pytest.raises(NoReverseMatch):
        reverse("calendar:add-matter", args=[matter.id])

    url = reverse("calendar:add-matter-origin", args=[matter.id, "matters"])
    assert url == f"/events/add/{matter.id}/matters"
