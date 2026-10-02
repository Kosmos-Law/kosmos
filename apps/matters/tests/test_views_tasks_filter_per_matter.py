"""Each matter's Tasks tab keeps its own filter: one set on one matter does
not follow the user to another, and Restore Defaults resets only the tab it
is pressed on."""

import pytest
from django.urls import reverse

from apps.matters.models import Matter
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_matter(user, contact, practice_area):
    return Matter.objects.create(
        name="Second Matter",
        status="Open",
        practice_area=practice_area,
        client=contact,
        user=user,
    )


@pytest.fixture
def tasks(user, matter, second_matter):
    made = {}
    for on in (matter, second_matter):
        for status in ("Pending", "Complete"):
            made[on.id, status] = Task.objects.create(
                user=user, matter=on, description=f"{status} task", status=status
            )
    return made


def _listed(client, matter):
    response = client.get(reverse("matters:tasks-list", args=[matter.id]))
    return {task.status for task in response.context["objects"]}, response


def test_filter_set_on_one_matter_stays_there(client, matter, second_matter, tasks):
    client.post(
        reverse("matters:tasks-filter", args=[matter.id]), {"status": "Complete"}
    )

    statuses, response = _listed(client, matter)
    assert statuses == {"Complete"}
    assert response.context["custom_filter_active"] is True

    statuses, response = _listed(client, second_matter)
    assert statuses == {"Pending"}
    assert response.context["custom_filter_active"] is False


def test_each_matter_keeps_its_own_session_key(client, matter, second_matter):
    client.post(reverse("matters:tasks-filter-importance", args=[matter.id, 7]))
    client.post(
        reverse("matters:tasks-filter-sort", args=[second_matter.id, "description"])
    )
    session = client.session
    assert session[f"matter_tasks_filter_{matter.id}"]["importance"] == 7
    assert "order_by" not in session[f"matter_tasks_filter_{matter.id}"]
    assert (
        session[f"matter_tasks_filter_{second_matter.id}"]["order_by"] == "description"
    )
    assert "importance" not in session[f"matter_tasks_filter_{second_matter.id}"]
    assert "matter_tasks_filter" not in session


def test_restore_defaults_leaves_the_other_matters_filter(
    client, matter, second_matter, tasks
):
    for on in (matter, second_matter):
        client.post(
            reverse("matters:tasks-filter", args=[on.id]), {"status": "Complete"}
        )

    client.post(
        reverse("matters:tasks-filter", args=[matter.id]), {"restore_defaults": "1"}
    )
    assert _listed(client, matter)[0] == {"Pending"}
    assert _listed(client, second_matter)[0] == {"Complete"}
