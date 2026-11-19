"""Upcoming Events: the pending events the user may see, soonest first,
the ones gone by still pending among them."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.calendar.models import Event
from apps.dash.events import EVENT_LIMIT, events_context
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return CustomUser.objects.create(username="Ollie", email="ollie@example.com")


def _event(**kwargs):
    kwargs.setdefault("status", "Pending")
    return Event.objects.create(description="Site visit", **kwargs)


def _events(user):
    today = timezone.localdate()
    return list(events_context(user, today)["upcoming_events"])


def test_past_due_pending_events_stay_and_lead(user):
    today = timezone.localdate()
    upcoming = _event(date=today + timedelta(days=3))
    past = _event(date=today - timedelta(days=1))
    assert _events(user) == [past, upcoming]


def test_resolved_and_undated_events_are_left_off(user):
    today = timezone.localdate()
    _event(status="Complete", date=today - timedelta(days=1))
    _event(status="Missed", date=today - timedelta(days=2))
    _event(date=None)
    assert _events(user) == []


def test_the_row_holds_seven(user):
    today = timezone.localdate()
    for offset in range(EVENT_LIMIT + 2):
        _event(date=today + timedelta(days=offset))
    assert len(_events(user)) == EVENT_LIMIT


def test_the_dates_the_cards_name(user):
    today = timezone.localdate()
    context = events_context(user, today)
    assert context["tomorrow"] == today + timedelta(days=1)
    assert context["yesterday"] == today - timedelta(days=1)


def test_a_restricted_user_sees_only_their_matters_and_the_firms():
    restricted_user = CustomUser.objects.create(
        username="Rita", email="rita@example.com", perm_all_matters=False
    )
    today = timezone.localdate()
    mine = Matter.objects.create(name="Assigned Matter", status="Open")
    mine.members.add(restricted_user)
    theirs = Matter.objects.create(name="Unassigned Matter", status="Open")
    on_mine = _event(date=today, matter=mine)
    _event(date=today + timedelta(days=1), matter=theirs)
    firm_wide = _event(date=today + timedelta(days=2))
    assert _events(restricted_user) == [on_mine, firm_wide]


def _client(user):
    user.last_dash_check = timezone.localdate()
    user.save(update_fields=["last_dash_check"])
    client = Client()
    client.force_login(user)
    return client


def test_the_page_and_the_section_draw_the_cards(user):
    today = timezone.localdate()
    event = _event(date=today, party="Smith")
    client = _client(user)
    for url in (reverse("dash:index"), reverse("dash:events-section")):
        html = client.get(url).content.decode()
        assert "<h2>Upcoming Events</h2>" in html
        assert 'class="event-card is-soon"' in html
        assert reverse("calendar:detail", args=[event.id]) in html


def test_with_nothing_pending_the_section_is_empty(user):
    html = _client(user).get(reverse("dash:events-section")).content.decode()
    assert "Upcoming Events" not in html


def test_a_card_completes_its_event_without_opening_it(user):
    event = _event(date=timezone.localdate())
    client = _client(user)
    html = client.get(reverse("dash:events-section")).content.decode()
    complete = reverse("calendar:set-status", args=[event.id, "Complete"])
    assert complete in html
    assert reverse("calendar:set-status", args=[event.id, "Missed"]) in html
    # the card's own click leaves its foot alone
    assert "click[!event.target.closest('.event-card-actions')]" in html

    response = client.post(complete)
    assert response.status_code == 204
    assert response.headers["HX-Trigger"] == "eventsChanged"
    event.refresh_from_db()
    assert event.status == "Complete"
    html = client.get(reverse("dash:events-section")).content.decode()
    assert "Upcoming Events" not in html
