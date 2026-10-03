"""A link cannot change or delete a task: those views answer only to POST."""

import pytest
from django.urls import NoReverseMatch, reverse

from apps.tasks.models import Task, TaskNote

pytestmark = pytest.mark.django_db


def _urls(task, user, matter):
    return {
        "delete": reverse("tasks:delete", args=[task.id]),
        "toggle": reverse("tasks:task-status", args=[task.id]),
        "status": reverse("tasks:set-status", args=[task.id, "on-hold"]),
        "importance": reverse("tasks:task-importance", args=[task.id, 7]),
        "user": reverse("tasks:task-user", args=[task.id, user.id]),
        "matter": reverse("tasks:task-matter", args=[task.id, 0]),
    }


def test_get_changes_nothing(client, task, user, matter):
    for name, url in _urls(task, user, matter).items():
        assert client.get(url).status_code == 405, name
    task.refresh_from_db()
    assert task.status == "Pending"
    assert task.importance == 4
    assert task.matter == matter


def test_post_sets_status_importance_user_and_matter(client, task, matter):
    from apps.accounts.models import CustomUser

    other = CustomUser.objects.create(username="Paz", email="paz@example.com")
    urls = _urls(task, other, matter)
    for name in ("status", "importance", "user", "matter"):
        assert client.post(urls[name]).status_code == 200, name
    task.refresh_from_db()
    assert task.status == "On hold"
    assert task.importance == 7
    assert task.user == other
    assert task.matter is None


def test_delete_answers_to_post_and_delete(client, task, user, matter):
    url = reverse("tasks:delete", args=[task.id])
    # The Edit Task dialog's Delete button sends hx-delete.
    assert client.delete(url).status_code == 204
    assert not Task.objects.filter(pk=task.id).exists()

    again = Task.objects.create(user=user, description="Another task")
    assert client.post(reverse("tasks:delete", args=[again.id])).status_code == 204
    assert not Task.objects.filter(pk=again.id).exists()


def test_note_delete_is_post_only(client, task, user):
    note = TaskNote.objects.create(task=task, user=user, details="Keep me")
    url = reverse("tasks:delete-note", args=[note.id])
    assert client.get(url).status_code == 405
    assert TaskNote.objects.filter(pk=note.id).exists()
    assert client.post(url).status_code == 302
    assert not TaskNote.objects.filter(pk=note.id).exists()


def test_quick_add_is_post_only(client):
    url = reverse("tasks:add-quick")
    assert client.get(url).status_code == 405
    assert client.get(url, {"description": "Planted by a link"}).status_code == 405
    assert not Task.objects.exists()
    # A post with no description field is an empty line, not a server error.
    assert client.post(url).status_code == 204
    assert not Task.objects.exists()


def test_clear_completed_route_is_gone(client, task):
    """Nothing on any page called it, and a GET deleted every completed task
    in the current filter."""
    with pytest.raises(NoReverseMatch):
        reverse("tasks:clear")
    Task.objects.filter(pk=task.id).update(status="Complete")
    assert client.get("/tasks/clear/").status_code == 404
    assert Task.objects.filter(pk=task.id).exists()


def test_row_controls_post(client, task):
    """The list's status, priority and user menus send what the views accept."""
    session = client.session
    session["tasks_filter"] = {"status": ["Pending"], "filter_label": "all"}
    session.save()
    body = client.get(reverse("tasks:list")).content.decode()
    for name, args in (
        ("tasks:set-status", [task.id, "complete"]),
        ("tasks:task-importance", [task.id, 7]),
        ("tasks:task-user", [task.id, task.user_id]),
    ):
        url = reverse(name, args=args)
        assert f'hx-post="{url}"' in body, name
        assert f'hx-get="{url}"' not in body, name
