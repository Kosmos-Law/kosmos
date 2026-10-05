"""The task form has no matter check of its own: a task on no matter is
the firm's (Admin), and the ModelForm's own field handles the rest."""

import pytest

from apps.tasks.forms import TaskForm

pytestmark = pytest.mark.django_db


def test_form_has_no_clean_matter_hook():
    assert not hasattr(TaskForm, "clean_matter")


def test_task_on_no_matter_is_valid(user):
    form = TaskForm(
        {
            "description": "Order toner",
            "user": user.id,
            "matter": "",
            "importance": "4",
            "status": "Pending",
            "date_due": "",
        },
        user=user,
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["matter"] is None
