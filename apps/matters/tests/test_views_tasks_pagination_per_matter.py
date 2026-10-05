"""Each matter's Tasks tab keeps its own page: page 3 of one matter's tasks
must not open another matter's tab on an empty page."""

import pytest
from django.urls import reverse

from apps.matters.models import Matter
from apps.matters.tasks.views import pagination_key
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
def many_tasks(user, matter, second_matter):
    """Two pages of tasks on each matter, so a shared key would turn both."""
    for on in (matter, second_matter):
        for n in range(25):
            Task.objects.create(
                user=user, matter=on, description=f"Task {n}", status="Pending"
            )


def _page(client, matter):
    response = client.get(reverse("matters:tasks-list", args=[matter.id]))
    assert response.status_code == 200
    return response.context["pagination"].number, response.context["session_key"]


def test_the_page_key_names_the_matter(client, matter, second_matter, many_tasks):
    _, key = _page(client, matter)
    _, other_key = _page(client, second_matter)
    assert key == pagination_key(matter.id)
    assert key != other_key


def test_a_page_turned_on_one_matter_leaves_the_other_on_page_one(
    client, matter, second_matter, many_tasks
):
    _, key = _page(client, matter)
    client.get(
        reverse(
            "management:change-page",
            kwargs={"session_key": key, "trigger_key": "tasksListChanged", "page": 2},
        )
    )
    assert _page(client, matter)[0] == 2
    assert _page(client, second_matter)[0] == 1
