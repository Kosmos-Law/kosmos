"""Removing a checklist announces the change with the event the tasks tab
and the matter Tasks tab reload on, so the row's checklist badge goes."""

import pytest
from django.urls import reverse

from apps.checklists.models import Checklist

pytestmark = pytest.mark.django_db


def test_remove_sends_the_trigger_the_lists_hear(client, task):
    Checklist.objects.create(task=task, name="Filing steps")
    response = client.post(reverse("checklists:remove-checklist", args=[task.id]))
    assert response.status_code == 204
    assert response.headers["HX-Trigger"] == "tasksListChanged"
    assert not Checklist.objects.filter(task=task).exists()
