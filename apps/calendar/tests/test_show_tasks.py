"""The calendar can show the user's open tasks beside its events: each a
chip that opens the task, with a box that marks it done, and a drag that
moves its due date."""

from datetime import date

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db

MARCH = {"start": "2030-03-01", "end": "2030-03-31"}


@pytest.fixture
def other_user():
    return CustomUser.objects.create(username="Nico", email="nico@example.com")


@pytest.fixture
def tasks(user, other_user, matter):
    return {
        "open": Task.objects.create(
            user=user, description="Open", date_due=date(2030, 3, 4), status="Pending"
        ),
        "on_matter": Task.objects.create(
            user=user,
            matter=matter,
            description="Draft",
            date_due=date(2030, 3, 5),
            status="In Progress",
        ),
        "done": Task.objects.create(
            user=user, description="Done", date_due=date(2030, 3, 4), status="Complete"
        ),
        "undated": Task.objects.create(user=user, description="Undated"),
        "theirs": Task.objects.create(
            user=other_user, description="Theirs", date_due=date(2030, 3, 4)
        ),
    }


def _toolbar(client):
    return client.get(reverse("calendar:overlays")).content.decode()


def _feed(client):
    return {
        row["id"]: row for row in client.get(reverse("calendar:feed"), MARCH).json()
    }


def test_tasks_are_off_by_default(client, tasks):
    assert not any(key.startswith("task-") for key in _feed(client))
    assert client.get(reverse("calendar:index")).context["show_tasks"] is False


def test_the_toggle(client, tasks):
    response = client.post(reverse("calendar:show-tasks", args=["on"]))

    assert response.status_code == 204
    assert response["HX-Trigger"] == "eventsChanged"
    assert client.get(reverse("calendar:index")).context["show_tasks"] is True
    assert reverse("calendar:show-tasks", args=["off"]) in _toolbar(client)

    client.post(reverse("calendar:show-tasks", args=["off"]))
    assert client.get(reverse("calendar:index")).context["show_tasks"] is False
    assert client.post(reverse("calendar:show-tasks", args=["no"])).status_code == 400


def test_only_the_users_open_dated_tasks_show(client, tasks):
    client.post(reverse("calendar:show-tasks", args=["on"]))

    feed = _feed(client)
    shown = {key for key in feed if key.startswith("task-")}

    assert shown == {f"task-{tasks['open'].id}", f"task-{tasks['on_matter'].id}"}
    row = feed[f"task-{tasks['on_matter'].id}"]
    assert row["title"] == "Sample Test Matter - Draft"
    assert row["allDay"] is True
    assert row["start"] == "2030-03-05"
    assert row["className"] == "fc-event-task"
    assert row["durationEditable"] is False
    assert row["extendedProps"] == {"kind": "task", "task_id": tasks["on_matter"].id}


def test_the_box_marks_the_task_done(client, tasks):
    response = client.post(reverse("calendar:task-done", args=[tasks["open"].id]))

    assert response.status_code == 204
    assert response["HX-Trigger"] == "tasksListChanged"
    tasks["open"].refresh_from_db()
    assert tasks["open"].status == "Complete"
    assert tasks["open"].date_completed is not None


def test_a_drag_moves_the_due_date(client, tasks):
    response = client.post(
        reverse("calendar:task-date", args=[tasks["open"].id]),
        {"date_due": "2030-03-11"},
    )

    assert response.status_code == 204
    tasks["open"].refresh_from_db()
    assert tasks["open"].date_due == date(2030, 3, 11)


def test_an_unreadable_date_changes_nothing(client, tasks):
    response = client.post(
        reverse("calendar:task-date", args=[tasks["open"].id]), {"date_due": "soon"}
    )

    assert response.status_code == 400
    tasks["open"].refresh_from_db()
    assert tasks["open"].date_due == date(2030, 3, 4)


def test_the_toolbar_offers_the_toggle(client):
    assert reverse("calendar:show-tasks", args=["on"]) in _toolbar(client)
    assert "Show my tasks" in _toolbar(client)
