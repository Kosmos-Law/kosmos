"""Multi-select on the event lists and the bulk change of status."""

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.calendar.models import Event
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


def _event(matter=None, **fields):
    fields = {"date": "2030-03-04", "status": "Pending"} | fields
    return Event.objects.create(matter=matter, **fields)


def _firm_list(client):
    client.post(reverse("calendar:view-mode", args=["list"]))
    return client.get(reverse("calendar:list"))


def _matter_list(client, matter):
    client.post(reverse("matters:events-view-mode", args=[matter.id, "list"]))
    return client.get(reverse("matters:events", args=[matter.id]))


def test_the_firm_list_has_a_box_for_each_event_and_one_for_all(client, matter):
    event = _event(matter, description="Hearing")

    body = _firm_list(client).content.decode()

    assert reverse("calendar:toggle-select", args=[event.id]) in body
    assert reverse("calendar:select-all") in body
    # nothing is ticked, so the toolbar is the list's usual one
    assert reverse("calendar:bulk-set-status") not in body
    assert reverse("calendar:filter") in body


def test_ticking_an_event_swaps_the_toolbar_for_the_bulk_actions(client, matter):
    event = _event(matter)

    response = client.post(reverse("calendar:toggle-select", args=[event.id]))

    assert response.status_code == 204
    assert response["HX-Trigger"] == "eventsChanged"
    listing = _firm_list(client)
    assert listing.context["selected_events"] == [event.id]
    body = listing.content.decode()
    assert reverse("calendar:bulk-set-status") in body
    assert reverse("calendar:clear-selection") in body
    # ticking it again clears it
    client.post(reverse("calendar:toggle-select", args=[event.id]))
    assert _firm_list(client).context["selected_events"] == []


def test_select_all_ticks_the_page_and_then_clears_it(client, matter):
    events = [_event(matter), _event(matter)]

    client.post(reverse("calendar:select-all"))
    listing = _firm_list(client)
    assert sorted(listing.context["selected_events"]) == [e.id for e in events]
    assert listing.context["all_selected"] is True

    client.post(reverse("calendar:select-all"))
    assert _firm_list(client).context["selected_events"] == []


def test_the_selected_events_take_the_status_and_the_selection_clears(client, matter):
    first, second, other = _event(matter), _event(matter), _event(matter)
    for event in (first, second):
        client.post(reverse("calendar:toggle-select", args=[event.id]))

    response = client.post(reverse("calendar:bulk-set-status"), {"status": "Complete"})

    assert response.status_code == 204
    assert response["HX-Trigger"] == "eventsChanged"
    statuses = {e.id: e.status for e in Event.objects.all()}
    assert statuses == {
        first.id: "Complete",
        second.id: "Complete",
        other.id: "Pending",
    }
    assert _firm_list(client).context["selected_events"] == []
    # the change is in each event's history
    assert first.history.first().status == "Complete"


def test_an_unknown_status_or_an_empty_selection_is_refused(client, matter):
    event = _event(matter)
    url = reverse("calendar:bulk-set-status")

    assert client.post(url, {"status": "Complete"}).status_code == 400
    client.post(reverse("calendar:toggle-select", args=[event.id]))
    assert client.post(url, {"status": "Done"}).status_code == 400
    assert client.post(url).status_code == 400
    event.refresh_from_db()
    assert event.status == "Pending"


def test_the_selection_routes_take_a_post(client, matter):
    event = _event(matter)

    for url in (
        reverse("calendar:toggle-select", args=[event.id]),
        reverse("calendar:select-all"),
        reverse("calendar:clear-selection"),
        reverse("calendar:bulk-set-status"),
    ):
        assert client.get(url).status_code == 405


def test_a_matters_tab_has_its_own_selection(client, matter, practice_area):
    elsewhere = Matter.objects.create(
        name="Another Matter", status="Open", practice_area=practice_area
    )
    here, there = _event(matter), _event(elsewhere)
    toggle = reverse("calendar:toggle-select-matter", args=[matter.id, here.id])

    response = client.post(toggle)

    assert response.status_code == 204
    assert response["HX-Trigger"] == "matterEventChanged"
    listing = _matter_list(client, matter)
    assert listing.context["selected_events"] == [here.id]
    body = listing.content.decode()
    assert toggle in body
    assert reverse("calendar:bulk-set-status-matter", args=[matter.id]) in body
    # the firm list's selection and the other matter's are untouched
    assert _firm_list(client).context["selected_events"] == []
    assert _matter_list(client, elsewhere).context["selected_events"] == []
    # an event on another matter is not this tab's to tick
    wrong = reverse("calendar:toggle-select-matter", args=[matter.id, there.id])
    assert client.post(wrong).status_code == 404

    client.post(
        reverse("calendar:bulk-set-status-matter", args=[matter.id]),
        {"status": "Missed"},
    )
    here.refresh_from_db()
    there.refresh_from_db()
    assert (here.status, there.status) == ("Missed", "Pending")
    assert _matter_list(client, matter).context["selected_events"] == []


def test_a_matters_select_all_ticks_the_tabs_events(client, matter):
    shown = _event(matter)
    _event(matter, status="Complete")  # the tab opens on Pending

    client.post(reverse("calendar:select-all-matter", args=[matter.id]))

    assert _matter_list(client, matter).context["selected_events"] == [shown.id]
    # the calendar view of the tab keeps its own toolbar
    client.post(reverse("matters:events-view-mode", args=[matter.id, "calendar"]))
    body = client.get(reverse("matters:events", args=[matter.id])).content.decode()
    assert reverse("calendar:bulk-set-status-matter", args=[matter.id]) not in body


def test_a_limited_user_cannot_tick_or_change_another_matters_event(matter):
    from django.test import Client

    limited = CustomUser.objects.create(
        username="Lim", email="lim@example.com", user_rate=100, perm_all_matters=False
    )
    client = Client()
    client.force_login(limited)
    client.get("/dash/")
    event = _event(matter)

    assert (
        client.post(reverse("calendar:toggle-select", args=[event.id])).status_code
        == 403
    )
    assert (
        client.post(reverse("calendar:select-all-matter", args=[matter.id])).status_code
        == 403
    )
    # an id that reached the session some other way is still left alone
    session = client.session
    session["selected_events"] = [event.id]
    session.save()
    response = client.post(reverse("calendar:bulk-set-status"), {"status": "Complete"})
    assert response.status_code == 400
    event.refresh_from_db()
    assert event.status == "Pending"


# --- move, assign, delete ---------------------------------------------------


def _tick(client, *events):
    for event in events:
        client.post(reverse("calendar:toggle-select", args=[event.id]))


def _invite(client, event, email):
    client.post(
        reverse("calendar:guest-add", args=[event.id]),
        {"email": email, "name": ""},
        HTTP_HX_REQUEST="true",
    )


@pytest.fixture
def inviting(settings):
    settings.CALENDAR_INBOUND_ADDRESS = "calendar@mail.example.com"


def test_the_bulk_toolbar_offers_move_assign_and_delete(client, matter):
    _tick(client, _event(matter))

    body = _firm_list(client).content.decode()

    for name in ("bulk-move", "bulk-assign", "bulk-delete"):
        assert reverse(f"calendar:{name}") in body
    assert "Delete 1 selected event?" in body


def test_move_shifts_the_selected_events_and_keeps_their_length(client, matter):
    one_day = _event(matter)
    several = _event(matter, date="2030-03-04", end_date="2030-03-06")
    other = _event(matter)
    _tick(client, one_day, several)
    url = reverse("calendar:bulk-move")

    dialog = client.get(url)
    assert dialog.status_code == 200
    assert "2 events selected." in dialog.content.decode()

    response = client.post(url, {"days": "14"})

    assert response.status_code == 204
    assert response["HX-Trigger"] == "eventsChanged"
    for event in (one_day, several, other):
        event.refresh_from_db()
    assert str(one_day.date) == "2030-03-18" and one_day.end_date is None
    assert (str(several.date), str(several.end_date)) == ("2030-03-18", "2030-03-20")
    assert str(other.date) == "2030-03-04"
    assert _firm_list(client).context["selected_events"] == []


def test_move_goes_back_with_a_negative_number_and_refuses_none(client, matter):
    event = _event(matter)
    _tick(client, event)
    url = reverse("calendar:bulk-move")

    for bad in ("0", "", "soon", "99999"):
        response = client.post(url, {"days": bad})
        assert response.status_code == 200  # the dialog again, with the error
    event.refresh_from_db()
    assert str(event.date) == "2030-03-04"
    assert _firm_list(client).context["selected_events"] == [event.id]

    client.post(url, {"days": "-3"})
    event.refresh_from_db()
    assert str(event.date) == "2030-03-01"


def test_moving_an_event_sends_its_guests_the_new_date(
    client, matter, inviting, mailoutbox
):
    invited = _event(matter, description="Mediation", start_time="09:00")
    quiet = _event(matter, description="Deadline")
    _invite(client, invited, "ann@example.org")
    _tick(client, invited, quiet)
    sent = len(mailoutbox)

    dialog = client.get(reverse("calendar:bulk-move")).content.decode()
    assert "1 of them has guests" in dialog

    client.post(reverse("calendar:bulk-move"), {"days": "7"})

    assert len(mailoutbox) == sent + 1
    assert mailoutbox[-1].subject == "Updated invitation: Mediation"
    assert mailoutbox[-1].to == ["ann@example.org"]


def test_assign_replaces_the_assignees_and_none_makes_them_the_firms(
    client, user, matter
):
    other = CustomUser.objects.create(
        username="Ann", email="ann@example.com", user_rate=100
    )
    first, second = _event(matter), _event(matter)
    first.assignees.set([other])
    _tick(client, first, second)
    url = reverse("calendar:bulk-assign")

    assert client.get(url).status_code == 200
    response = client.post(url, {"assignees": [user.id]})

    assert response.status_code == 204
    assert list(first.assignees.all()) == [user]
    assert list(second.assignees.all()) == [user]
    assert _firm_list(client).context["selected_events"] == []

    _tick(client, first)
    client.post(url, {})
    assert list(first.assignees.all()) == []
    assert list(second.assignees.all()) == [user]


def test_delete_removes_the_selected_events_and_tells_their_guests(
    client, matter, inviting, mailoutbox
):
    invited = _event(matter, description="Mediation", start_time="09:00")
    quiet, kept = _event(matter), _event(matter)
    _invite(client, invited, "ann@example.org")
    _tick(client, invited, quiet)

    body = _firm_list(client).content.decode()
    assert "Delete 2 selected events?" in body
    assert "The guests of 1 of them will be told it is cancelled." in body

    response = client.post(reverse("calendar:bulk-delete"))

    assert response.status_code == 204
    assert list(Event.objects.all()) == [kept]
    assert mailoutbox[-1].subject == "Cancelled: Mediation"
    assert _firm_list(client).context["selected_events"] == []


def test_the_actions_refuse_an_empty_selection_and_delete_takes_a_post(client, matter):
    event = _event(matter)

    for name in ("bulk-move", "bulk-assign"):
        assert client.get(reverse(f"calendar:{name}")).status_code == 400
        assert (
            client.post(reverse(f"calendar:{name}"), {"days": "1"}).status_code == 400
        )
    assert client.post(reverse("calendar:bulk-delete")).status_code == 400
    _tick(client, event)
    assert client.get(reverse("calendar:bulk-delete")).status_code == 405
    assert Event.objects.filter(pk=event.pk).exists()


def test_a_matters_tab_moves_assigns_and_deletes_its_own(client, user, matter):
    here = _event(matter)
    unassigned = _event(None)
    client.post(reverse("calendar:toggle-select-matter", args=[matter.id, here.id]))
    # an id from elsewhere in this tab's selection is left alone
    session = client.session
    session[f"selected_events_{matter.id}"] = [here.id, unassigned.id]
    session.save()

    dialog = client.get(reverse("calendar:bulk-move-matter", args=[matter.id]))
    assert reverse("calendar:bulk-move-matter", args=[matter.id]) in (
        dialog.content.decode()
    )
    response = client.post(
        reverse("calendar:bulk-move-matter", args=[matter.id]), {"days": "1"}
    )
    assert response["HX-Trigger"] == "matterEventChanged"
    here.refresh_from_db()
    unassigned.refresh_from_db()
    assert (str(here.date), str(unassigned.date)) == ("2030-03-05", "2030-03-04")

    client.post(reverse("calendar:toggle-select-matter", args=[matter.id, here.id]))
    client.post(
        reverse("calendar:bulk-assign-matter", args=[matter.id]),
        {"assignees": [user.id]},
    )
    assert list(here.assignees.all()) == [user]

    client.post(reverse("calendar:toggle-select-matter", args=[matter.id, here.id]))
    client.post(reverse("calendar:bulk-delete-matter", args=[matter.id]))
    assert list(Event.objects.all()) == [unassigned]
