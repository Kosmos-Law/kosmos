"""The list's sort buttons reverse on a second click."""

import pytest
from django.urls import reverse

from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def tasks(user):
    made = {}
    for description, status, importance in (
        ("Alpha task", "Pending", 2),
        ("Bravo task", "In progress", 7),
        ("Charlie task", "On hold", 4),
    ):
        made[description] = Task.objects.create(
            user=user, description=description, status=status, importance=importance
        )
    return made


@pytest.fixture
def all_client(client):
    session = client.session
    session["tasks_filter"] = {
        "status": ["Pending", "In progress", "On hold"],
        "filter_label": "all",
        "order_by": "date_due",
    }
    session.save()
    return client


def _order(response, field):
    return [getattr(task, field) for task in response.context["objects"]]


def test_status_sort_reverses(all_client, tasks):
    url = reverse("tasks:filter-sort", args=["status"])
    first = _order(all_client.post(url), "status")
    second = _order(all_client.post(url), "status")
    assert first == ["In progress", "On hold", "Pending"]
    assert second == ["Pending", "On hold", "In progress"]
    assert all_client.session["tasks_filter"]["order_by"] == "-status"


def test_flag_button_toggles(all_client, tasks):
    # Status leads the priority sort, so compare within one status.
    Task.objects.update(status="Pending")
    # The flag button posts "-importance": highest first on the first click.
    url = reverse("tasks:filter-sort", args=["-importance"])
    assert _order(all_client.post(url), "importance") == [7, 4, 2]
    assert _order(all_client.post(url), "importance") == [2, 4, 7]
    assert _order(all_client.post(url), "importance") == [7, 4, 2]


def test_other_columns_still_toggle(all_client, tasks):
    url = reverse("tasks:filter-sort", args=["description"])
    all_client.post(url)
    assert all_client.session["tasks_filter"]["order_by"] == "description"
    all_client.post(url)
    assert all_client.session["tasks_filter"]["order_by"] == "-description"
    all_client.post(url)
    assert all_client.session["tasks_filter"]["order_by"] == "description"
