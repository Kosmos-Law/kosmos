"""The template form takes the task it was opened from as ``task_id`` in the
query string or the body. A value that is not an id answers 400."""

import pytest
from django.urls import reverse

from apps.checklists.models import Checklist, ChecklistTemplate

pytestmark = pytest.mark.django_db


def test_edit_refuses_a_task_id_that_is_not_a_number(client, second_template):
    url = reverse("checklists:edit-checklist-template", args=[second_template.id])
    assert client.post(url + "?task_id=abc", {"name": "Renamed"}).status_code == 400
    response = client.post(url, {"name": "Renamed", "task_id": "1 OR 1=1"})
    assert response.status_code == 400
    assert client.get(url + "?task_id=abc").status_code == 400
    second_template.refresh_from_db()
    assert second_template.name == "Closing steps"


def test_add_refuses_a_task_id_that_is_not_a_number(client):
    url = reverse("checklists:add-checklist-template")
    response = client.post(url + "?task_id=abc", {"name": "New steps"})
    assert response.status_code == 400
    assert not ChecklistTemplate.objects.filter(name="New steps").exists()


def test_a_real_task_id_still_attaches(client, task, second_template):
    url = reverse("checklists:edit-checklist-template", args=[second_template.id])
    response = client.post(f"{url}?task_id={task.id}", {"name": "Closing steps"})
    assert response.status_code == 302
    assert Checklist.objects.get(task=task).template == second_template


def test_no_task_id_is_the_plain_template_form(client, second_template):
    url = reverse("checklists:edit-checklist-template", args=[second_template.id])
    assert client.get(url).status_code == 200
    assert client.post(url, {"name": "Closing steps"}).status_code == 204
