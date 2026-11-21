"""The bulk toolbar offers Assign: one click hands every selected task to
a colleague, from the tasks page and from a matter's Tasks tab alike."""

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def colleague():
    return CustomUser.objects.create(
        username="bob", email="bob@example.com", user_rate=100
    )


def test_the_tasks_toolbar_offers_assign(client, task, colleague):
    client.post(reverse("tasks:toggle-select", args=[task.id]))
    html = client.get(reverse("tasks:toolbar")).content.decode()

    assert "Assign" in html
    assert reverse("tasks:bulk-set-user") in html
    assert f'"user": "{colleague.id}"' in html


def test_a_matters_tasks_toolbar_offers_assign(client, task, matter, colleague):
    client.post(reverse("matters:tasks-toggle-select", args=[matter.id, task.id]))
    html = client.get(reverse("matters:tasks-index", args=[matter.id])).content.decode()

    assert reverse("matters:tasks-bulk-set-user", args=[matter.id]) in html
    assert f'"user": "{colleague.id}"' in html


def test_assigning_from_a_matter_hands_the_tasks_over(client, task, matter, colleague):
    client.post(reverse("matters:tasks-toggle-select", args=[matter.id, task.id]))
    client.post(
        reverse("matters:tasks-bulk-set-user", args=[matter.id]),
        {"user": colleague.id},
    )

    task.refresh_from_db()
    assert task.user == colleague
