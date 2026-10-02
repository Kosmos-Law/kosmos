"""A task holds one checklist: attaching a second one is not a server error."""

import pytest
from django.urls import reverse

from apps.checklists.models import Checklist, ChecklistItem

pytestmark = pytest.mark.django_db


def _attach(client, task, template):
    return client.post(
        reverse("checklists:attach-checklist", args=[task.id]),
        {"template_id": template.id},
    )


def test_attach_copies_the_template(client, task, template):
    response = _attach(client, task, template)
    assert response.status_code == 302
    assert response.url == reverse("checklists:checklist-modal", args=[task.id])
    checklist = Checklist.objects.get(task=task)
    assert checklist.name == "Filing steps"
    assert [i.description for i in checklist.items.all()] == ["Proofread", "Serve"]


def test_second_attach_keeps_the_first_checklist(
    client, task, template, second_template
):
    _attach(client, task, template)
    ChecklistItem.objects.filter(description="Proofread").update(is_complete=True)

    response = _attach(client, task, second_template)
    assert response.status_code == 302
    assert response.url == reverse("checklists:checklist-modal", args=[task.id])

    checklist = Checklist.objects.get(task=task)
    assert checklist.template == template
    assert checklist.items.count() == 2
    assert checklist.items.get(description="Proofread").is_complete


def test_saving_a_new_template_onto_a_task_that_has_a_checklist(
    client, task, template, second_template
):
    """New Checklist from the picker ends by attaching the template it made."""
    _attach(client, task, template)
    response = client.post(
        reverse("checklists:edit-checklist-template", args=[second_template.id])
        + f"?task_id={task.id}",
        {"name": "Closing steps"},
    )
    assert response.status_code == 302
    assert Checklist.objects.get(task=task).template == template
