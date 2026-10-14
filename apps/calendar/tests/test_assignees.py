"""An event is assigned to any number of people, or to nobody, which is the
firm's: the form ticks them, the titles carry their initials, and the
Assigned-to menu ticks any set of them."""

import json

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.calendar.events import assignees_label
from apps.calendar.filter import FIRM, assignee_tokens
from apps.calendar.models import Event

pytestmark = pytest.mark.django_db

MARCH = {"start": "2030-03-01", "end": "2030-03-31"}


@pytest.fixture
def ada():
    return CustomUser.objects.create(
        username="ada", first_name="Ada", last_name="Lovelace", initials="AL"
    )


@pytest.fixture
def nico():
    return CustomUser.objects.create(
        username="nico", first_name="Nico", last_name="Reyes", initials="NR"
    )


def _event(description, *assignees):
    event = Event.objects.create(
        date="2030-03-04", description=description, status="Pending", party="Client"
    )
    event.assignees.set(assignees)
    return event


@pytest.fixture
def events(user, ada, nico):
    return {
        "firm": _event("Firm meeting"),
        "mine": _event("Mine", user),
        "ada": _event("Ada's", ada),
        "both": _event("Hearing", ada, nico),
    }


def _feed(client):
    return {
        row["id"]: row for row in client.get(reverse("calendar:feed"), MARCH).json()
    }


def _shown(client, events):
    ids = set(_feed(client))
    return {name for name, event in events.items() if str(event.id) in ids}


def _tick(client, token):
    return client.post(reverse("calendar:filter-assigned", args=[token]))


# --- the form --------------------------------------------------------------


def test_the_form_ticks_several_assignees(client, ada, nico):
    client.post(
        reverse("calendar:add"),
        {
            "date": "2030-03-04",
            "description": "Hearing",
            "status": "Pending",
            "party": "Client",
            "assignees": [ada.id, nico.id],
        },
    )

    event = Event.objects.get(description="Hearing")
    assert set(event.assignees.all()) == {ada, nico}
    assert event.assignee_initials == "AL, NR"


def test_nobody_ticked_is_the_firms(client):
    client.post(
        reverse("calendar:add"),
        {
            "date": "2030-03-04",
            "description": "Staff meeting",
            "status": "Pending",
            "party": "Client",
        },
    )

    event = Event.objects.get(description="Staff meeting")
    assert not event.assignees.exists()
    assert event.assignee_initials == ""


def test_the_form_offers_boxes_for_the_active_users(client, ada):
    body = client.get(reverse("calendar:add")).content.decode()

    assert 'type="checkbox" name="assignees"' in body
    assert "Ada Lovelace" in body
    assert "nobody means the firm" in body


# --- the titles ------------------------------------------------------------


def test_the_feed_title_carries_every_assignees_initials(client, events, ada, nico):
    row = _feed(client)[str(events["both"].id)]

    assert row["title"] == "Hearing - AL, NR"
    assert row["extendedProps"]["assignees"] == ["Ada", "Nico"]


def test_the_firms_event_has_no_initials(client, events):
    assert _feed(client)[str(events["firm"].id)]["title"] == "Firm meeting"


# --- the menu --------------------------------------------------------------


def test_nothing_ticked_shows_everything(client, events):
    assert _shown(client, events) == {"firm", "mine", "ada", "both"}
    assert client.get(reverse("calendar:index")).context["events_filter_assigned"] == ""


def test_ticking_firm_shows_the_firms_events(client, events):
    _tick(client, FIRM)

    assert _shown(client, events) == {"firm"}
    context = client.get(reverse("calendar:index")).context
    assert context["events_filter_assigned"] == "Firm"
    assert context["events_filter_assigned_values"] == [FIRM]


def test_ticks_add_up_and_a_second_tick_removes(client, events, user, ada):
    response = _tick(client, str(ada.id))
    assert response.status_code == 204
    assert json.loads(response["HX-Trigger"]) == {
        "eventsChanged": None,
        "assigneesToggled": None,
    }
    assert _shown(client, events) == {"ada", "both"}

    _tick(client, FIRM)
    _tick(client, str(user.id))
    assert _shown(client, events) == {"firm", "mine", "ada", "both"}
    assert client.get(reverse("calendar:index")).context["events_filter_assigned"] == (
        "3 assignees"
    )

    _tick(client, str(ada.id))
    assert _shown(client, events) == {"firm", "mine"}
    assert client.get(reverse("calendar:index")).context["events_filter_assigned"] == (
        "Firm, Ollie"
    )


def test_all_assignees_clears_the_ticks(client, events, ada):
    _tick(client, str(ada.id))

    client.post(reverse("calendar:filter-assigned-all"))

    assert _shown(client, events) == {"firm", "mine", "ada", "both"}


def test_the_menu_draws_the_ticks(client, ada):
    _tick(client, str(ada.id))

    menu = client.get(reverse("calendar:filter-menus")).content.decode()

    assert menu.count("icon-square-check") == 1
    assert "All assignees" in menu


def test_the_filter_dialog_ticks_the_same_set(client, events, ada, nico):
    client.post(
        reverse("calendar:filter"),
        {"assigned_to": [str(ada.id), str(nico.id)], "status": "Pending"},
    )

    assert _shown(client, events) == {"ada", "both"}
    page = client.get(reverse("calendar:index")).context
    assert page["events_filter_assigned"] == "Ada, Nico"


def test_a_choice_that_is_no_longer_offered_is_ignored(client, events):
    _tick(client, "9999")

    assert _shown(client, events) == {"firm", "mine", "ada", "both"}
    assert client.get(reverse("calendar:index")).context["events_filter_assigned"] == ""


def test_helpers():
    assert assignee_tokens(None) == []
    assert assignee_tokens("") == []
    assert assignee_tokens("3") == ["3"]
    assert assignee_tokens(["3", "", FIRM]) == ["3", FIRM]
    assert assignees_label([]) == ""
    assert assignees_label(["Ada"]) == "Ada"
    assert assignees_label(["Ada", "Nico"]) == "Ada, Nico"
    assert assignees_label(["A", "B", "C"]) == "3 assignees"


# --- the API ---------------------------------------------------------------


def test_the_api_lists_the_assignees(client, events, user):
    from apps.drafts.models import CompanionToken  # noqa: F401

    event = events["both"]
    assert event.assignee_names == ["Ada", "Nico"]
