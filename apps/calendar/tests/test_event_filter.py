"""The Filter Events dialog and the toolbar menus.

Matter and "Assigned to" are choices built for the user, not boxes holding
ids. The default filter (Pending) is what both views fall back to after
Restore Defaults, and the calendar view can fetch the menus' current state.
"""

import pytest
from django.urls import reverse

from apps.calendar.filter import EventFilter
from apps.calendar.models import Event
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db

MARCH = {"start": "2030-03-01", "end": "2030-03-31"}


@pytest.fixture
def statuses(matter):
    return {
        status: Event.objects.create(
            matter=matter,
            date="2030-03-04",
            description=f"{status} event",
            status=status,
        )
        for status in ("Pending", "Complete", "Missed")
    }


def _restore_defaults(client):
    return client.post(
        reverse(
            "management:clear-filters",
            kwargs={"session_key": "events_filter", "trigger": "eventsChanged"},
        )
    )


def test_matter_and_assignee_are_choices(client, user, matter):
    form = EventFilter({}, user=user).form

    assert (str(matter.id), matter.name) in form.fields["matter"].choices
    assert ("unassigned", "Unassigned") in form.fields["matter"].choices
    assert ("unassigned", "Firm") in form.fields["assigned_to"].choices
    assert str(user.id) in dict(form.fields["assigned_to"].choices)

    body = client.get(reverse("calendar:filter")).content.decode()
    assert '<select name="matter"' in body
    assert '<select name="assigned_to"' in body


def test_matter_choices_leave_out_closed_matters(user, matter, practice_area):
    closed = Matter.objects.create(
        name="Closed Matter", status="Closed", practice_area=practice_area
    )

    choices = dict(EventFilter({}, user=user).form.fields["matter"].choices)

    assert str(matter.id) in choices
    assert str(closed.id) not in choices


def test_applied_matter_and_assignee_filter_the_list(client, user, matter, statuses):
    mine = Event.objects.create(
        matter=None,
        date="2030-03-04",
        description="Assigned to me",
        status="Pending",
        assigned_to=user,
    )

    client.post(reverse("calendar:filter"), {"matter": matter.id, "status": ""})
    by_matter = client.get(reverse("calendar:index")).context["objects"]
    assert set(by_matter) == set(statuses.values())

    client.post(reverse("calendar:filter"), {"assigned_to": user.id, "status": ""})
    by_assignee = client.get(reverse("calendar:index")).context["objects"]
    assert list(by_assignee) == [mine]


def test_calendar_feed_defaults_to_pending(client, statuses):
    feed = client.get(reverse("calendar:feed"), MARCH).json()

    assert [row["id"] for row in feed] == [str(statuses["Pending"].id)]


def test_restore_defaults_means_pending_in_the_calendar_feed(client, statuses):
    client.post(reverse("calendar:filter-status-all"))
    everything = client.get(reverse("calendar:feed"), MARCH).json()
    assert len(everything) == 3

    _restore_defaults(client)

    feed = client.get(reverse("calendar:feed"), MARCH).json()
    assert [row["id"] for row in feed] == [str(statuses["Pending"].id)]


def test_restore_defaults_means_pending_in_the_list(client, statuses):
    client.post(reverse("calendar:view-mode", args=["list"]))
    client.post(reverse("calendar:filter-status-all"))

    _restore_defaults(client)

    response = client.get(reverse("calendar:list"))
    assert list(response.context["objects"]) == [statuses["Pending"]]
    assert response.context["events_filter_status"] == "Pending"


def test_menus_show_the_filter_as_it_now_stands(client, matter, statuses):
    client.post(reverse("calendar:filter"), {"matter": matter.id, "status": "Complete"})

    response = client.get(reverse("calendar:filter-menus"))

    assert response.context["events_filter_status"] == "Complete"
    assert response.context["events_filter_matter"] == matter.name

    _restore_defaults(client)

    response = client.get(reverse("calendar:filter-menus"))
    assert response.context["events_filter_status"] == "Pending"
    assert response.context["events_filter_matter"] == ""


def test_calendar_view_toolbar_refreshes_its_menus(client):
    body = client.get(reverse("calendar:index")).content.decode()

    assert reverse("calendar:filter-menus") in body
