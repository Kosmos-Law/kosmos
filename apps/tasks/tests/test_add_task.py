"""The Add Task dialog: what it saves, and what it does with bad input."""

import pytest
from django.urls import reverse

from apps.tasks.forms import TaskForm
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


def _data(user, **changes):
    return {
        "description": "Draft the motion",
        "user": user.id,
        "matter": "",
        "importance": "4",
        "status": "Pending",
        "date_due": "",
    } | changes


# -----------------------------------------------------
# an invalid post re-renders the dialog
# -----------------------------------------------------
def test_invalid_post_shows_the_form_again(client, user):
    response = client.post(reverse("tasks:add"), _data(user, description="abc"))
    assert response.status_code == 200
    assert "description" in response.context["form"].errors


def test_empty_description_is_a_form_error(client, user):
    response = client.post(reverse("tasks:add"), _data(user, description=""))
    assert response.status_code == 200
    assert "4 or more" in response.context["form"].errors["description"][0]
    assert not Task.objects.exists()


def test_form_without_a_description_is_invalid_not_an_exception(user):
    form = TaskForm(_data(user, description=""))
    assert not form.is_valid()
    assert "description" in form.errors


def test_empty_description_on_edit_is_a_form_error(client, task, user):
    response = client.post(
        reverse("tasks:edit", args=[task.id]), _data(user, description="")
    )
    assert response.status_code == 200
    assert "description" in response.context["form"].errors


# -----------------------------------------------------
# status
# -----------------------------------------------------
def test_add_honours_the_forms_status(client, user):
    response = client.post(reverse("tasks:add"), _data(user, status="In progress"))
    assert response.status_code == 204
    assert Task.objects.get(description="Draft the motion").status == "In progress"


def test_add_without_a_status_is_pending(client, user):
    data = _data(user)
    del data["status"]
    assert client.post(reverse("tasks:add"), data).status_code == 204
    assert Task.objects.get(description="Draft the motion").status == "Pending"


def test_board_column_is_only_the_starting_status(client, user):
    url = reverse("tasks:add") + "?status=on-hold"
    # The dialog opens showing the column's status...
    form = client.get(url).context["form"]
    assert form.initial["status"] == "On hold"
    # ...and the Status the user submits is what is saved.
    assert client.post(url, _data(user, status="In progress")).status_code == 204
    assert Task.objects.get(description="Draft the motion").status == "In progress"


def test_board_column_status_is_kept_when_left_alone(client, user):
    url = reverse("tasks:add") + "?status=on-hold"
    assert client.post(url, _data(user, status="On hold")).status_code == 204
    assert Task.objects.get(description="Draft the motion").status == "On hold"
