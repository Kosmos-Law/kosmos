"""Who may see, open and change calendar events.

A user limited to assigned matters reaches only the events on those matters,
plus events on no matter (those are the firm's). That holds for the list, the
calendar feed, every by-id view and the matter choices, and a delete is never
done by following a link.
"""

import json

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.calendar.models import Event
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_matter(practice_area):
    return Matter.objects.create(
        name="Unassigned Matter", status="Open", practice_area=practice_area
    )


@pytest.fixture
def restricted(matter):
    """A user limited to assigned matters, assigned only ``matter``."""
    user = CustomUser.objects.create(
        username="Rae",
        email="rae@example.com",
        user_rate=150,
        perm_all_matters=False,
    )
    user.set_password("clawboy")
    user.save()
    matter.members.add(user)
    return user


@pytest.fixture
def restricted_client(restricted):
    client = Client()
    client.force_login(restricted)
    client.get("/dash/")
    return client


def _event(matter, description, **extra):
    fields = {"date": "2030-03-04", "party": "Client", "status": "Pending"} | extra
    return Event.objects.create(matter=matter, description=description, **fields)


@pytest.fixture
def events(matter, other_matter):
    return {
        "mine": _event(matter, "On my matter"),
        "theirs": _event(other_matter, "On another matter"),
        "firm": _event(None, "Firm holiday"),
    }


# --- the list and the feed -------------------------------------------------


def test_list_holds_own_matters_and_firm_events_only(restricted_client, events):
    response = restricted_client.get(reverse("calendar:index"))

    assert set(response.context["objects"]) == {events["mine"], events["firm"]}
    assert b"On another matter" not in response.content


def test_list_is_complete_for_an_unrestricted_user(client, events):
    response = client.get(reverse("calendar:index"))

    assert set(response.context["objects"]) == set(events.values())


def test_feed_holds_own_matters_and_firm_events_only(restricted_client, events):
    feed = restricted_client.get(
        reverse("calendar:feed"), {"start": "2030-03-01", "end": "2030-03-31"}
    ).json()

    assert {row["id"] for row in feed} == {
        str(events["mine"].id),
        str(events["firm"].id),
    }


def test_matter_feed_needs_matter_access(restricted_client, events, matter):
    own = reverse("calendar:feed-matter", args=[matter.id])
    other = reverse("calendar:feed-matter", args=[events["theirs"].matter_id])

    assert restricted_client.get(own).status_code == 200
    assert restricted_client.get(other).status_code == 403


# --- by-id views -----------------------------------------------------------


def test_event_on_an_unassigned_matter_is_refused(restricted_client, events):
    theirs = events["theirs"]
    edit = reverse("calendar:edit", args=[theirs.id])
    delete = reverse("calendar:delete", args=[theirs.id])
    quick = reverse("calendar:quick-update", args=[theirs.id])

    assert restricted_client.get(edit).status_code == 403
    assert restricted_client.post(edit, {"description": "Taken"}).status_code == 403
    assert restricted_client.post(delete).status_code == 403
    assert restricted_client.delete(delete).status_code == 403
    moved = restricted_client.post(
        quick, json.dumps({"date": "2031-01-01"}), content_type="application/json"
    )
    assert moved.status_code == 403

    theirs.refresh_from_db()
    assert theirs.description == "On another matter"
    assert str(theirs.date) == "2030-03-04"


def test_own_and_firm_events_can_be_opened_and_moved(restricted_client, events):
    for event in (events["mine"], events["firm"]):
        edit = reverse("calendar:edit", args=[event.id])
        assert restricted_client.get(edit).status_code == 200

        moved = restricted_client.post(
            reverse("calendar:quick-update", args=[event.id]),
            json.dumps({"date": "2030-03-05"}),
            content_type="application/json",
        )
        assert moved.status_code == 204
        event.refresh_from_db()
        assert str(event.date) == "2030-03-05"


def test_delete_is_refused_on_get(client, event):
    response = client.get(reverse("calendar:delete", args=[event.id]))

    assert response.status_code == 405
    assert Event.objects.filter(pk=event.pk).exists()


@pytest.mark.parametrize("method", ["post", "delete"])
def test_delete_by_post_or_delete(client, event, method):
    response = getattr(client, method)(reverse("calendar:delete", args=[event.id]))

    assert response.status_code == 204
    assert not Event.objects.filter(pk=event.pk).exists()


# --- matter choices --------------------------------------------------------


def test_toolbar_matter_menu_lists_only_assigned_matters(
    restricted_client, matter, other_matter
):
    response = restricted_client.get(reverse("calendar:index"))

    assert list(response.context["matters"]) == [matter]


def test_add_form_offers_only_assigned_matters(restricted_client, matter, other_matter):
    form = restricted_client.get(reverse("calendar:add")).context["form"]

    assert list(form.fields["matter"].queryset) == [matter]


def test_add_form_cannot_be_opened_from_an_unassigned_matter(
    restricted_client, matter, other_matter
):
    own = reverse("calendar:add-matter-origin", args=[matter.id, "matters"])
    other = reverse("calendar:add-matter-origin", args=[other_matter.id, "matters"])

    assert restricted_client.get(own).status_code == 200
    assert restricted_client.get(other).status_code == 403


def test_event_cannot_be_put_on_an_unassigned_matter(
    restricted_client, events, other_matter
):
    data = {
        "matter": other_matter.id,
        "date": "2030-03-04",
        "party": "Client",
        "status": "Pending",
        "description": "Slipped in",
    }

    added = restricted_client.post(reverse("calendar:add"), data)
    edited = restricted_client.post(
        reverse("calendar:edit", args=[events["mine"].id]), data
    )

    for response in (added, edited):
        assert response.status_code == 200
        assert "matter" in response.context["form"].errors
    assert not Event.objects.filter(description="Slipped in").exists()


def test_filtering_by_an_unassigned_matter_shows_neither_it_nor_its_name(
    restricted_client, events, other_matter
):
    response = restricted_client.post(
        reverse("calendar:filter-matter", args=[other_matter.id])
    )

    assert other_matter.name.encode() not in response.content
    listed = restricted_client.get(reverse("calendar:index")).context["objects"]
    assert events["theirs"] not in listed
