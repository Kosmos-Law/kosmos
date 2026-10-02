"""The task list the classic chat context carries: open work first.

The list is cut to twenty rows, so the order decides what the model is
told about at all.
"""

import pytest

from apps.case.ai.context import format_tasks
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


def _lines(matter):
    return format_tasks(matter).split("\n")


def test_pending_tasks_come_before_completed(matter, user):
    Task.objects.create(
        matter=matter, user=user, description="Filed the answer", status="Complete"
    )
    Task.objects.create(
        matter=matter, user=user, description="Draft discovery", status="Pending"
    )
    lines = _lines(matter)
    assert "[PENDING]" in lines[0] and "Draft discovery" in lines[0]
    assert "[DONE]" in lines[1]


def test_most_important_pending_task_comes_first(matter, user):
    Task.objects.create(
        matter=matter, user=user, description="Low", status="Pending", importance=1
    )
    Task.objects.create(
        matter=matter, user=user, description="Top", status="Pending", importance=7
    )
    Task.objects.create(
        matter=matter, user=user, description="Normal", status="Pending", importance=4
    )
    assert [line.split(": ", 1)[1] for line in _lines(matter)] == [
        "Top",
        "Normal",
        "Low",
    ]


def test_soonest_due_first_within_an_importance(matter, user):
    Task.objects.create(
        matter=matter, user=user, description="No date", status="Pending"
    )
    Task.objects.create(
        matter=matter,
        user=user,
        description="Later",
        status="Pending",
        date_due="2026-03-01",
    )
    Task.objects.create(
        matter=matter,
        user=user,
        description="Sooner",
        status="Pending",
        date_due="2026-02-01",
    )
    lines = _lines(matter)
    assert "Sooner" in lines[0]
    assert "Later" in lines[1]
    assert "No date" in lines[2]


def test_completed_work_does_not_crowd_out_open_tasks(matter, user):
    """Twenty-five finished tasks and one open one: the cut keeps the open
    one. (It used to be filled with completed, least important rows.)"""
    for n in range(25):
        Task.objects.create(
            matter=matter,
            user=user,
            description=f"Finished item {n}",
            status="Complete",
            importance=1,
        )
    Task.objects.create(
        matter=matter, user=user, description="The open item", status="Pending"
    )
    lines = _lines(matter)
    assert len(lines) == 20
    assert "The open item" in lines[0]
