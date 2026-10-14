"""Pinned dates: a due date is suggestive unless the assignor makes it
pinned; a pinned date on a task handed to someone else is the assignor's (or
an admin's) alone to move."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.tasks.forms import TaskForm
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def colleague():
    return CustomUser.objects.create(
        username="Bob", email="bob@example.com", user_rate=100
    )


@pytest.fixture
def colleague_client(colleague):
    client = Client()
    client.force_login(colleague)
    client.get("/dash/")
    return client


@pytest.fixture
def admin_client():
    admin = CustomUser.objects.create(
        username="Ada", email="ada@example.com", user_rate=100, role="ADMIN"
    )
    client = Client()
    client.force_login(admin)
    client.get("/dash/")
    return client


@pytest.fixture
def handed_off(task, user, colleague):
    """``task``, given to Bob by Ollie with a pinned date, due 2024-12-07."""
    task.user = colleague
    task.assigned_by = user
    task.date_pinned = True
    task.save()
    return task


def _data(assignee, **changes):
    return {
        "description": "Draft the motion",
        "user": assignee.id,
        "matter": "",
        "importance": "4",
        "status": "Pending",
        "date_due": "2026-11-02",
        "date_pinned": "False",
    } | changes


def _toast(response):
    return response.headers.get("HX-Toast", "")


def _descriptions(response):
    return [t.description for t in response.context["objects"]]


# -----------------------------------------------------
# who the assignor is
# -----------------------------------------------------
def test_a_task_for_someone_else_records_who_gave_it(client, user, colleague):
    client.post(reverse("tasks:add"), _data(colleague))
    assert Task.objects.get().assigned_by == user


def test_a_date_is_suggestive_unless_pinned(client, user, colleague):
    client.post(reverse("tasks:add"), _data(colleague))
    assert not Task.objects.get().date_pinned
    Task.objects.all().delete()
    client.post(reverse("tasks:add"), _data(colleague, date_pinned="True"))
    assert Task.objects.get().date_pinned


def test_a_task_for_yourself_has_no_assignor(client, user):
    client.post(reverse("tasks:add"), _data(user))
    assert Task.objects.get().assigned_by is None


def test_reassigning_restamps_the_assignor(colleague_client, handed_off, colleague):
    third = CustomUser.objects.create(
        username="Cy", email="cy@example.com", user_rate=100
    )
    colleague_client.post(reverse("tasks:task-user", args=[handed_off.id, third.id]))
    handed_off.refresh_from_db()
    assert handed_off.assigned_by == colleague


def test_taking_a_task_on_yourself_clears_the_assignor(
    colleague_client, task, user, colleague
):
    task.assigned_by = user
    task.save()
    colleague_client.post(reverse("tasks:task-user", args=[task.id, colleague.id]))
    task.refresh_from_db()
    assert task.assigned_by is None


def test_an_edit_that_keeps_the_user_keeps_the_assignor(
    colleague_client, handed_off, user, colleague
):
    colleague_client.post(
        reverse("tasks:edit", args=[handed_off.id]),
        _data(colleague, description="Read about Gandhi again"),
    )
    handed_off.refresh_from_db()
    assert handed_off.assigned_by == user


# -----------------------------------------------------
# the inline date picker
# -----------------------------------------------------
def test_the_assignee_cannot_move_the_date(colleague_client, handed_off):
    response = colleague_client.post(
        reverse("tasks:date", args=[handed_off.id]), {"date_due": "2025-01-31"}
    )
    assert response.status_code == 204
    assert "pinned. Only Ollie can move it" in _toast(response)
    handed_off.refresh_from_db()
    assert str(handed_off.date_due) == "2024-12-07"


def test_the_assignor_can(client, handed_off):
    client.post(reverse("tasks:date", args=[handed_off.id]), {"date_due": "2025-01-31"})
    handed_off.refresh_from_db()
    assert str(handed_off.date_due) == "2025-01-31"


def test_an_admin_can(admin_client, handed_off):
    admin_client.post(
        reverse("tasks:date", args=[handed_off.id]), {"date_due": "2025-01-31"}
    )
    handed_off.refresh_from_db()
    assert str(handed_off.date_due) == "2025-01-31"


def test_a_suggestive_date_is_the_assignees_to_move(colleague_client, handed_off):
    handed_off.date_pinned = False
    handed_off.save()
    colleague_client.post(
        reverse("tasks:date", args=[handed_off.id]), {"date_due": "2025-01-31"}
    )
    handed_off.refresh_from_db()
    assert str(handed_off.date_due) == "2025-01-31"


def test_a_task_nobody_handed_over_is_anyones_to_move(colleague_client, task):
    colleague_client.post(
        reverse("tasks:date", args=[task.id]), {"date_due": "2025-01-31"}
    )
    task.refresh_from_db()
    assert str(task.date_due) == "2025-01-31"


def test_the_matter_tab_refuses_too(colleague_client, handed_off, matter):
    response = colleague_client.post(
        reverse("matters:tasks-date", args=[matter.id, handed_off.id]),
        {"date_due": "2025-01-31"},
    )
    assert "Only Ollie" in _toast(response)
    handed_off.refresh_from_db()
    assert str(handed_off.date_due) == "2024-12-07"


# -----------------------------------------------------
# Edit Task
# -----------------------------------------------------
def test_the_form_shows_the_assignee_a_disabled_date(handed_off, colleague, user):
    form = TaskForm(instance=handed_off, user=colleague)
    assert form.fields["date_due"].disabled
    assert form.fields["date_pinned"].disabled
    assert "Pinned by Ollie" in form.fields["date_due"].widget.attrs["title"]
    assert not TaskForm(instance=handed_off, user=user).fields["date_due"].disabled


def test_the_assignee_cannot_unpin_a_date(colleague_client, handed_off, colleague):
    colleague_client.post(
        reverse("tasks:edit", args=[handed_off.id]),
        _data(colleague, date_pinned="False", date_due="2025-01-31"),
    )
    handed_off.refresh_from_db()
    assert handed_off.date_pinned
    assert str(handed_off.date_due) == "2024-12-07"


def test_the_assignor_can_unpin_it(client, handed_off, colleague):
    client.post(
        reverse("tasks:edit", args=[handed_off.id]),
        _data(colleague, date_pinned="False"),
    )
    handed_off.refresh_from_db()
    assert not handed_off.date_pinned


def test_a_posted_date_from_the_assignee_is_ignored(
    colleague_client, handed_off, colleague
):
    response = colleague_client.post(
        reverse("tasks:edit", args=[handed_off.id]),
        _data(colleague, description="Read about Gandhi again", date_due="2025-01-31"),
    )
    assert response.status_code == 204
    handed_off.refresh_from_db()
    assert handed_off.description == "Read about Gandhi again"
    assert str(handed_off.date_due) == "2024-12-07"


# -----------------------------------------------------
# bulk changes
# -----------------------------------------------------
def _select(client, *tasks):
    for t in tasks:
        client.post(reverse("tasks:toggle-select", args=[t.id]))


def test_bulk_set_date_skips_handed_over_tasks(colleague_client, handed_off, colleague):
    own = Task.objects.create(
        user=colleague, description="Bob's own task", status="Pending"
    )
    _select(colleague_client, handed_off, own)
    response = colleague_client.post(
        reverse("tasks:bulk-set-due-date"), {"date_due": "2025-01-31"}
    )
    assert "1 task(s) skipped" in _toast(response)
    own.refresh_from_db()
    handed_off.refresh_from_db()
    assert str(own.date_due) == "2025-01-31"
    assert str(handed_off.date_due) == "2024-12-07"


def test_bulk_clear_date_skips_them_too(colleague_client, handed_off):
    _select(colleague_client, handed_off)
    response = colleague_client.post(reverse("tasks:bulk-clear-due-date"))
    assert "1 task(s) skipped" in _toast(response)
    handed_off.refresh_from_db()
    assert str(handed_off.date_due) == "2024-12-07"


def test_bulk_update_applies_the_rest_but_not_the_date(colleague_client, handed_off):
    _select(colleague_client, handed_off)
    response = colleague_client.post(
        reverse("tasks:bulk-update"),
        {"status": "In progress", "importance": "", "date_due": "2025-01-31"},
    )
    assert "1 task(s) skipped" in _toast(response)
    handed_off.refresh_from_db()
    assert handed_off.status == "In progress"
    assert str(handed_off.date_due) == "2024-12-07"


# -----------------------------------------------------
# what each person sees
# -----------------------------------------------------
def test_the_assignee_sees_a_lock_and_the_assignor_a_picker(
    client, colleague_client, handed_off
):
    for c in (client, colleague_client):
        c.post(reverse("tasks:filter-quick", args=["all"]))
        c.post(reverse("tasks:filter-user", args=[0]))
    theirs = colleague_client.get(reverse("tasks:list")).content.decode()
    assert "Pinned by Ollie" in theirs
    assert "2024-12-07" in theirs
    assert "task-date-link" not in theirs

    mine = client.get(reverse("tasks:list")).content.decode()
    assert "Pinned by Ollie" not in mine
    assert "task-date-link" in mine
    assert "task-date-pin" in mine


def test_the_detail_dialog_names_the_assignor(colleague_client, handed_off):
    html = colleague_client.get(
        reverse("tasks:detail", args=[handed_off.id])
    ).content.decode()
    assert "Date pinned by Ollie" in html


# -----------------------------------------------------
# the toolbar pin: your watch-list beside your own tasks
# -----------------------------------------------------
def _own_chip(client, user):
    client.post(reverse("tasks:filter-quick", args=["all"]))
    client.post(reverse("tasks:filter-user", args=[user.id]))


def test_the_pin_shows_the_tasks_you_pinned_for_others(
    client, user, colleague, handed_off
):
    Task.objects.create(
        user=colleague,
        assigned_by=user,
        description="Unpinned for Bob",
        status="Pending",
    )
    Task.objects.create(user=user, description="Ollie's own task", status="Pending")
    _own_chip(client, user)
    assert _descriptions(client.get(reverse("tasks:list"))) == ["Ollie's own task"]

    response = client.post(reverse("tasks:toggle-pinned"))
    user.refresh_from_db()
    assert user.show_pinned_tasks
    assert set(_descriptions(response)) == {
        "Ollie's own task",
        "Read about Mohandas Gandhi",
    }
    # The chip still reads as Ollie's.
    assert response.context["user_id"] == user.id

    response = client.post(reverse("tasks:toggle-pinned"))
    assert _descriptions(response) == ["Ollie's own task"]


def test_the_date_window_still_applies_to_your_pins(
    client, user, colleague, handed_off
):
    # Only the one field: a full save bumps the session check and signs
    # the test client out.
    user.show_pinned_tasks = True
    user.save(update_fields=["show_pinned_tasks"])
    client.post(reverse("tasks:filter-user", args=[user.id]))
    # The default "Today" window: a 2024 pin is past due, so it shows.
    client.post(reverse("tasks:filter-quick", args=["today"]))
    assert "Read about Mohandas Gandhi" in _descriptions(
        client.get(reverse("tasks:list"))
    )
    handed_off.date_due = "2099-01-01"
    handed_off.save()
    assert _descriptions(client.get(reverse("tasks:list"))) == []


def test_all_users_is_unchanged_by_the_pin(client, user, colleague, handed_off):
    # Only the one field: a full save bumps the session check and signs
    # the test client out.
    user.show_pinned_tasks = True
    user.save(update_fields=["show_pinned_tasks"])
    client.post(reverse("tasks:filter-quick", args=["all"]))
    client.post(reverse("tasks:filter-user", args=[0]))
    assert _descriptions(client.get(reverse("tasks:list"))) == [
        "Read about Mohandas Gandhi"
    ]


def test_the_board_shows_your_pins_too(client, user, colleague, handed_off):
    # Only the one field: a full save bumps the session check and signs
    # the test client out.
    user.show_pinned_tasks = True
    user.save(update_fields=["show_pinned_tasks"])
    _own_chip(client, user)
    client.post(reverse("tasks:view-mode", args=["board"]))
    response = client.get(reverse("tasks:list"))
    cards = [t.description for c in response.context["columns"] for t in c["tasks"]]
    assert "Read about Mohandas Gandhi" in cards


def test_the_matter_tab_has_the_same_pin(client, user, colleague, handed_off, matter):
    client.post(reverse("matters:tasks-filter-user", args=[matter.id, user.id]))
    assert (
        _descriptions(client.get(reverse("matters:tasks-list", args=[matter.id]))) == []
    )
    client.post(reverse("matters:tasks-toggle-pinned", args=[matter.id]))
    assert _descriptions(
        client.get(reverse("matters:tasks-list", args=[matter.id]))
    ) == ["Read about Mohandas Gandhi"]


def test_restore_defaults_keeps_the_pin(client, user, colleague, handed_off):
    # Only the one field: a full save bumps the session check and signs
    # the test client out.
    user.show_pinned_tasks = True
    user.save(update_fields=["show_pinned_tasks"])
    client.get(reverse("tasks:filter-default"))
    user.refresh_from_db()
    assert user.show_pinned_tasks
    assert "Read about Mohandas Gandhi" in _descriptions(
        client.get(reverse("tasks:list"))
    )


def test_the_toolbar_button_reads_the_preference(client, user):
    html = client.get(reverse("tasks:list")).content.decode()
    assert "Show the tasks you pinned for others" in html
    client.post(reverse("tasks:toggle-pinned"))
    html = client.get(reverse("tasks:list")).content.decode()
    assert "Hide the tasks you pinned for others" in html
