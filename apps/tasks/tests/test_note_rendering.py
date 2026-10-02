"""Task notes are rendered as Markdown and emitted as safe markup, so markup
typed into one must come out as text."""

import pytest
from django.urls import reverse

from apps.tasks.models import Task, TaskNote

pytestmark = pytest.mark.django_db


def test_markup_in_a_task_note_is_shown_as_text(client, user):
    task = Task.objects.create(
        description="Call the clerk", user=user, status="Pending"
    )
    TaskNote.objects.create(
        task=task, user=user, details='**done** <script>alert("x")</script>'
    )

    for name in ("tasks:detail", "tasks:detail-notes"):
        body = client.get(reverse(name, args=[task.id])).content.decode()

        assert "<script>alert" not in body
        assert "&lt;script&gt;" in body
        assert "<strong>done</strong>" in body
