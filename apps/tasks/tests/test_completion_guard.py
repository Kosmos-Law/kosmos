"""What a user is told when a task cannot be completed because its checklist
is unfinished: a warning toast, on every path that sets one task's status."""

import json

import pytest
from django.urls import reverse

from apps.checklists.models import Checklist, ChecklistItem
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db

MESSAGE = "Please complete all checklist items before marking this task as done."


@pytest.fixture
def blocked_task(user):
    task = Task.objects.create(
        user=user, description="File the brief", status="Pending"
    )
    checklist = Checklist.objects.create(task=task, name="Filing")
    ChecklistItem.objects.create(checklist=checklist, description="Proofread")
    return task


@pytest.mark.parametrize(
    "name,args", [("tasks:set-status", ["complete"]), ("tasks:task-status", [])]
)
def test_refusal_is_a_warning_toast(client, blocked_task, name, args):
    response = client.post(reverse(name, args=[blocked_task.id, *args]))
    assert response.status_code == 204
    toast = json.loads(response.headers["HX-Toast"])
    # "warning" is one of the four types the toast script knows.
    assert toast["type"] == "warning"
    assert toast["message"] == MESSAGE
    blocked_task.refresh_from_db()
    assert blocked_task.status == "Pending"
