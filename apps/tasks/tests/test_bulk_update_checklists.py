"""Bulk Update cannot complete a task whose checklist is unfinished."""

import json

import pytest
from django.urls import reverse

from apps.checklists.models import Checklist, ChecklistItem
from apps.tasks.forms import BulkTasksForm
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def blocked_task(user):
    """A task with one unticked checklist item."""
    task = Task.objects.create(
        user=user, description="File the brief", status="Pending"
    )
    checklist = Checklist.objects.create(task=task, name="Filing")
    ChecklistItem.objects.create(checklist=checklist, description="Proofread")
    return task


def _select(client, *task_ids):
    session = client.session
    session["selected_tasks"] = list(task_ids)
    session.save()


def test_bulk_update_skips_tasks_with_unfinished_checklists(client, task, blocked_task):
    _select(client, task.id, blocked_task.id)
    response = client.post(
        reverse("tasks:bulk-update"), {"status": "Complete", "importance": "7"}
    )
    assert response.status_code == 204
    task.refresh_from_db()
    blocked_task.refresh_from_db()
    assert task.status == "Complete" and task.importance == 7
    # Skipped whole, as the Edit Task dialog refuses the whole save.
    assert blocked_task.status == "Pending" and blocked_task.importance == 4

    toast = json.loads(response.headers["HX-Toast"])
    assert toast["type"] == "warning"
    assert toast["message"] == "1 task(s) skipped. Complete their checklists first."


def test_bulk_update_to_another_status_is_not_guarded(client, blocked_task):
    _select(client, blocked_task.id)
    response = client.post(reverse("tasks:bulk-update"), {"status": "On hold"})
    assert "HX-Toast" not in response.headers
    blocked_task.refresh_from_db()
    assert blocked_task.status == "On hold"


def test_bulk_update_completes_a_task_whose_checklist_is_done(client, blocked_task):
    ChecklistItem.objects.filter(checklist__task=blocked_task).update(is_complete=True)
    _select(client, blocked_task.id)
    response = client.post(reverse("tasks:bulk-update"), {"status": "Complete"})
    assert "HX-Toast" not in response.headers
    blocked_task.refresh_from_db()
    assert blocked_task.status == "Complete"


def test_skip_messages_carry_no_em_dash(client, blocked_task):
    _select(client, blocked_task.id)
    response = client.post(reverse("tasks:bulk-set-status"), {"status": "Complete"})
    message = json.loads(response.headers["HX-Toast"])["message"]
    assert message == "1 task(s) skipped. Complete their checklists first."

    _select(client, blocked_task.id)
    response = client.post(
        reverse("tasks:board-bulk-move"),
        json.dumps({"status_slug": "complete"}),
        content_type="application/json",
    )
    assert response.json()["message"] == message


def test_no_change_choices_carry_no_em_dash():
    form = BulkTasksForm()
    labels = []
    for name in ("status", "importance", "user", "matter"):
        labels.append(str(list(form.fields[name].choices)[0][1]))
    assert labels == ["No change"] * 4
