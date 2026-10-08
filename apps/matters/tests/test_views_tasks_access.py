"""A matter's Tasks tab: which matters its forms offer, and which requests
its change views answer to.

The tab itself is behind matter membership. What it must not do is hand a
user limited to assigned matters the rest of the firm's matter list, or
change a task from a plain link.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.matters.models import Matter
from apps.tasks.models import Task

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


@pytest.fixture
def task(user, matter):
    return Task.objects.create(
        user=user, matter=matter, description="File the brief", status="Pending"
    )


def _choice_ids(form):
    return {m.id for m in form.fields["matter"].queryset}


# -----------------------------------------------------
# matter choices
# -----------------------------------------------------
def test_add_form_offers_only_own_matters(restricted_client, matter, other_matter):
    response = restricted_client.get(reverse("matters:tasks-add", args=[matter.id]))
    assert _choice_ids(response.context["form"]) == {matter.id}
    assert other_matter.name not in response.content.decode()


def test_add_refuses_a_matter_that_is_not_offered(
    restricted, restricted_client, matter, other_matter
):
    response = restricted_client.post(
        reverse("matters:tasks-add", args=[matter.id]),
        {
            "description": "Planted task",
            "user": restricted.id,
            "matter": other_matter.id,
            "importance": "4",
            "status": "Pending",
        },
    )
    assert response.status_code == 200
    assert "matter" in response.context["form"].errors
    assert not Task.objects.filter(description="Planted task").exists()


def test_add_form_on_a_closed_matter_still_offers_that_matter(client, matter):
    matter.status = "Closed"
    matter.save()
    response = client.get(reverse("matters:tasks-add", args=[matter.id]))
    assert matter.id in _choice_ids(response.context["form"])


def test_filter_dialog_offers_only_own_matters(restricted_client, matter, other_matter):
    response = restricted_client.get(reverse("matters:tasks-filter", args=[matter.id]))
    offered = {m.id for m in response.context["filter"].form.fields["matter"].queryset}
    assert offered == {matter.id}


def test_bulk_update_offers_and_accepts_only_own_matters(
    restricted_client, matter, other_matter, task
):
    session = restricted_client.session
    session[f"selected_tasks_{matter.id}"] = [task.id]
    session.save()
    url = reverse("matters:tasks-bulk-update", args=[matter.id])
    assert _choice_ids(restricted_client.get(url).context["form"]) == {matter.id}

    response = restricted_client.post(url, {"matter": other_matter.id})
    assert response.status_code == 200
    assert "matter" in response.context["form"].errors
    task.refresh_from_db()
    assert task.matter == matter


# -----------------------------------------------------
# change views answer only to POST
# -----------------------------------------------------
def test_get_changes_nothing(client, matter, task, user):
    urls = [
        reverse("matters:tasks-delete", args=[matter.id, task.id]),
        reverse("matters:tasks-status", args=[matter.id, task.id]),
        reverse("matters:tasks-set-status", args=[matter.id, task.id, "on-hold"]),
        reverse("matters:tasks-importance", args=[matter.id, task.id, 7]),
        reverse("matters:tasks-user", args=[matter.id, task.id, user.id]),
        reverse("matters:tasks-add-quick", args=[matter.id]),
    ]
    for url in urls:
        assert client.get(url).status_code == 405, url
    task.refresh_from_db()
    assert task.status == "Pending"
    assert task.importance == 4
    assert Task.objects.count() == 1


def test_quick_add_post_without_a_description_is_not_an_error(client, matter):
    url = reverse("matters:tasks-add-quick", args=[matter.id])
    assert client.post(url).status_code == 204
    assert not Task.objects.exists()


def test_post_still_changes_the_task(client, matter, task):
    url = reverse("matters:tasks-set-status", args=[matter.id, task.id, "on-hold"])
    assert client.post(url).status_code == 204
    url = reverse("matters:tasks-importance", args=[matter.id, task.id, 7])
    assert client.post(url).status_code == 204
    task.refresh_from_db()
    assert task.status == "On hold"
    assert task.importance == 7

    url = reverse("matters:tasks-delete", args=[matter.id, task.id])
    assert client.post(url).status_code == 204
    assert not Task.objects.filter(pk=task.id).exists()


def test_status_menu_posts(client, matter, task):
    body = client.get(reverse("matters:tasks-list", args=[matter.id])).content.decode()
    url = reverse("matters:tasks-set-status", args=[matter.id, task.id, "complete"])
    assert f'hx-post="{url}"' in body
    assert f'hx-get="{url}"' not in body
