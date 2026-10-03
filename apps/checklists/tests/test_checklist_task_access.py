"""A task's checklist follows the task: a user limited to assigned matters
cannot open, attach, tick, refresh or remove one on another matter's task."""

import pytest
from django.urls import reverse

from apps.checklists.models import Checklist, ChecklistItem
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_checklist(other_task, template):
    checklist = Checklist.objects.create(
        task=other_task, template=template, name=template.name
    )
    ChecklistItem.objects.create(checklist=checklist, description="Proofread")
    return checklist


def test_other_matters_checklist_cannot_be_opened(restricted_client, other_checklist):
    task_id = other_checklist.task_id
    for name in ("checklist-modal", "attach-checklist", "checklist-search"):
        url = reverse(f"checklists:{name}", args=[task_id])
        assert restricted_client.get(url).status_code == 403, name


def test_other_matters_checklist_cannot_be_changed(
    restricted_client, other_task, other_checklist, second_template
):
    item = other_checklist.items.get()
    posts = [
        (reverse("checklists:toggle-checklist-item", args=[item.id]), {}),
        (reverse("checklists:refresh-checklist", args=[other_task.id]), {}),
        (reverse("checklists:remove-checklist", args=[other_task.id]), {}),
        (
            reverse("checklists:attach-checklist", args=[other_task.id]),
            {"template_id": second_template.id},
        ),
    ]
    for url, data in posts:
        assert restricted_client.post(url, data).status_code == 403, url

    item.refresh_from_db()
    assert not item.is_complete
    assert (
        Checklist.objects.get(task=other_task).template_id
        == other_checklist.template_id
    )


def test_checklist_cannot_be_attached_through_the_template_form(
    restricted_client, other_task, second_template
):
    """The template form takes a task id in the query string or the body."""
    url = reverse("checklists:edit-checklist-template", args=[second_template.id])
    for target, data in (
        (f"{url}?task_id={other_task.id}", {"name": "Renamed"}),
        (url, {"name": "Renamed", "task_id": other_task.id}),
    ):
        assert restricted_client.post(target, data).status_code == 403
    assert not Checklist.objects.filter(task=other_task).exists()
    second_template.refresh_from_db()
    assert second_template.name == "Closing steps"


def test_own_and_matterless_tasks_checklists_work(
    restricted, restricted_client, task, template
):
    firm_task = Task.objects.create(
        user=restricted, description="Order more toner", status="Pending"
    )
    for target in (task, firm_task):
        attach = reverse("checklists:attach-checklist", args=[target.id])
        assert restricted_client.get(attach).status_code == 200
        response = restricted_client.post(attach, {"template_id": template.id})
        assert response.status_code == 302
        modal = reverse("checklists:checklist-modal", args=[target.id])
        assert restricted_client.get(modal).status_code == 200
        item = target.checklist.items.first()
        toggle = reverse("checklists:toggle-checklist-item", args=[item.id])
        assert restricted_client.post(toggle).status_code == 200
        item.refresh_from_db()
        assert item.is_complete
