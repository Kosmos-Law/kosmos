"""The matter Events tab sorts only by its own columns: a sort key that is
not one of them is refused on the way in and ignored on the way out, so a
session value cannot reach order_by() and raise."""

import pytest
from django.urls import reverse

from apps.calendar.models import Event
from apps.matters.events.get_event_data import sort_session_key

pytestmark = pytest.mark.django_db


@pytest.fixture
def events(user, matter):
    for party, date in (("Court", "2026-01-02"), ("Client", "2026-01-01")):
        Event.objects.create(
            user=user, matter=matter, party=party, date=date, status="Pending"
        )


def _parties(client, matter):
    response = client.get(reverse("matters:events", args=[matter.id]))
    assert response.status_code == 200
    return [event.party for event in response.context["events"]]


def test_unknown_sort_key_is_404(client, matter):
    url = reverse("matters:events-filter-sort", args=[matter.id, "bogus"])
    assert client.post(url).status_code == 404
    assert sort_session_key(matter.id) not in client.session


def test_a_bad_stored_key_falls_back_to_date(client, matter, events):
    session = client.session
    session[sort_session_key(matter.id)] = "no_such_column"
    session.save()
    assert _parties(client, matter) == ["Client", "Court"]


def test_a_known_sort_key_applies_and_reverses(client, matter, events):
    url = reverse("matters:events-filter-sort", args=[matter.id, "party"])
    assert client.post(url).status_code == 204
    assert _parties(client, matter) == ["Client", "Court"]
    assert client.post(url).status_code == 204
    assert _parties(client, matter) == ["Court", "Client"]
