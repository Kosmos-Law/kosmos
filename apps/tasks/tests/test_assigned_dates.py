"""Dates on assigned tasks: the due date of a task someone else assigned is
the assignor's (or an admin's) alone to set, move or clear. A task nobody
handed over is its user's to schedule."""

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
    """``task``, given to Bob by Ollie, due 2024-12-07."""
    task.user = colleague
    task.assigned_by = user
    task.save()
    return task


def _third():
    return CustomUser.objects.create(
        username="Cy", email="cy@example.com", user_rate=100
    )


def _data(assignee, **changes):
    return {
        "description": "Draft the motion",
        "user": assignee.id,
        "matter": "",
        "importance": "4",
        "status": "Pending",
        "date_due": "2026-11-02",
    } | changes


def _select(client, *tasks):
    for t in tasks:
        client.post(reverse("tasks:toggle-select", args=[t.id]))


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


def test_a_task_for_yourself_has_no_assignor(client, user):
    client.post(reverse("tasks:add"), _data(user))
    assert Task.objects.get().assigned_by is None


def test_handing_over_your_own_task_stamps_you(client, task, user, colleague):
    client.post(reverse("tasks:task-user", args=[task.id, colleague.id]))
    task.refresh_from_db()
    assert task.assigned_by == user


def test_bulk_reassigning_stamps_you_too(client, task, user, colleague):
    _select(client, task)
    client.post(reverse("tasks:bulk-set-user"), {"user": colleague.id})
    task.refresh_from_db()
    assert task.user == colleague
    assert task.assigned_by == user


def test_an_edit_that_keeps_the_user_keeps_the_assignor(
    colleague_client, handed_off, user, colleague
):
    colleague_client.post(
        reverse("tasks:edit", args=[handed_off.id]),
        _data(colleague, description="Read about Gandhi again"),
    )
    handed_off.refresh_from_db()
    assert handed_off.assigned_by == user


def test_the_assignee_passing_the_task_on_keeps_the_assignor(
    colleague_client, handed_off, user
):
    third = _third()
    colleague_client.post(reverse("tasks:task-user", args=[handed_off.id, third.id]))
    handed_off.refresh_from_db()
    assert handed_off.user == third
    assert handed_off.assigned_by == user


def test_passing_it_around_and_back_changes_nothing(
    colleague_client, handed_off, user, colleague
):
    third = _third()
    colleague_client.post(reverse("tasks:task-user", args=[handed_off.id, third.id]))
    colleague_client.post(
        reverse("tasks:task-user", args=[handed_off.id, colleague.id])
    )
    handed_off.refresh_from_db()
    assert handed_off.user == colleague
    assert handed_off.assigned_by == user
    response = colleague_client.post(
        reverse("tasks:date", args=[handed_off.id]), {"date_due": "2025-01-31"}
    )
    assert "Only Ollie" in _toast(response)


def test_the_assignor_passing_it_on_stays_the_assignor(client, handed_off, user):
    third = _third()
    client.post(reverse("tasks:task-user", args=[handed_off.id, third.id]))
    handed_off.refresh_from_db()
    assert handed_off.assigned_by == user


def test_the_assignor_taking_it_back_clears_the_stamp(client, handed_off, user):
    client.post(reverse("tasks:task-user", args=[handed_off.id, user.id]))
    handed_off.refresh_from_db()
    assert handed_off.assigned_by is None


def test_an_admin_reassigning_takes_the_assignors_place(admin_client, handed_off):
    third = _third()
    admin_client.post(reverse("tasks:task-user", args=[handed_off.id, third.id]))
    handed_off.refresh_from_db()
    assert handed_off.assigned_by.username == "Ada"


# -----------------------------------------------------
# the inline date picker
# -----------------------------------------------------
def test_the_assignee_cannot_move_the_date(colleague_client, handed_off):
    response = colleague_client.post(
        reverse("tasks:date", args=[handed_off.id]), {"date_due": "2025-01-31"}
    )
    assert response.status_code == 204
    assert "Only Ollie can move this date" in _toast(response)
    handed_off.refresh_from_db()
    assert str(handed_off.date_due) == "2024-12-07"


def test_nor_set_one_on_an_undated_assigned_task(client, colleague_client, colleague):
    client.post(reverse("tasks:add"), _data(colleague, date_due=""))
    task = Task.objects.get()
    response = colleague_client.post(
        reverse("tasks:date", args=[task.id]), {"date_due": "2025-01-31"}
    )
    assert "Only Ollie" in _toast(response)
    task.refresh_from_db()
    assert task.date_due is None


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
    assert "Assigned by Ollie" in form.fields["date_due"].widget.attrs["title"]
    assert not TaskForm(instance=handed_off, user=user).fields["date_due"].disabled


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


def test_the_assignor_can_clear_the_date(client, handed_off, colleague):
    client.post(
        reverse("tasks:edit", args=[handed_off.id]), _data(colleague, date_due="")
    )
    handed_off.refresh_from_db()
    assert handed_off.date_due is None


# -----------------------------------------------------
# bulk changes
# -----------------------------------------------------
def test_bulk_set_date_skips_assigned_tasks(colleague_client, handed_off, colleague):
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


def test_the_assignor_bulk_dates_their_assigned_tasks(client, handed_off):
    _select(client, handed_off)
    client.post(reverse("tasks:bulk-set-due-date"), {"date_due": "2025-01-31"})
    handed_off.refresh_from_db()
    assert str(handed_off.date_due) == "2025-01-31"


# -----------------------------------------------------
# what each person sees
# -----------------------------------------------------
def test_the_assignee_sees_text_and_the_assignor_a_picker(
    client, colleague_client, handed_off
):
    for c in (client, colleague_client):
        c.post(reverse("tasks:filter-quick", args=["all"]))
        c.post(reverse("tasks:filter-user", args=[0]))
    theirs = colleague_client.get(reverse("tasks:list")).content.decode()
    assert "Assigned by Ollie" in theirs
    assert "2024-12-07" in theirs
    assert "task-date-link" not in theirs
    assert "icon-pin task-date" not in theirs

    mine = client.get(reverse("tasks:list")).content.decode()
    assert "Assigned by Ollie" not in mine
    assert "task-date-link" in mine


def test_the_detail_dialog_names_the_assignor(colleague_client, handed_off):
    html = colleague_client.get(
        reverse("tasks:detail", args=[handed_off.id])
    ).content.decode()
    assert "Assigned by Ollie, who alone can move the date" in html


# -----------------------------------------------------
# the watch-list toggle: tasks you assigned beside your own
# -----------------------------------------------------
def _own_chip(client, user):
    client.post(reverse("tasks:filter-quick", args=["all"]))
    client.post(reverse("tasks:filter-user", args=[user.id]))


def _watching(user):
    # Only the one field: a full save bumps the session check and signs
    # the test client out.
    user.show_assigned_tasks = True
    user.save(update_fields=["show_assigned_tasks"])


def test_the_toggle_shows_the_tasks_you_assigned(client, user, colleague, handed_off):
    Task.objects.create(
        user=colleague,
        assigned_by=user,
        description="Undated, for Bob",
        status="Pending",
    )
    Task.objects.create(user=colleague, description="Bob's own task", status="Pending")
    Task.objects.create(user=user, description="Ollie's own task", status="Pending")
    _own_chip(client, user)
    assert _descriptions(client.get(reverse("tasks:list"))) == ["Ollie's own task"]

    response = client.post(reverse("tasks:toggle-assigned"))
    user.refresh_from_db()
    assert user.show_assigned_tasks
    assert set(_descriptions(response)) == {
        "Ollie's own task",
        "Read about Mohandas Gandhi",
        "Undated, for Bob",
    }
    # The chip still reads as Ollie's.
    assert response.context["user_id"] == user.id

    response = client.post(reverse("tasks:toggle-assigned"))
    assert _descriptions(response) == ["Ollie's own task"]


def test_the_date_window_still_applies(client, user, colleague, handed_off):
    _watching(user)
    client.post(reverse("tasks:filter-user", args=[user.id]))
    # The default "Today" window: a 2024 date is past due, so it shows.
    client.post(reverse("tasks:filter-quick", args=["today"]))
    assert "Read about Mohandas Gandhi" in _descriptions(
        client.get(reverse("tasks:list"))
    )
    handed_off.date_due = "2099-01-01"
    handed_off.save()
    assert _descriptions(client.get(reverse("tasks:list"))) == []


def test_all_users_is_unchanged_by_the_toggle(client, user, colleague, handed_off):
    _watching(user)
    client.post(reverse("tasks:filter-quick", args=["all"]))
    client.post(reverse("tasks:filter-user", args=[0]))
    assert _descriptions(client.get(reverse("tasks:list"))) == [
        "Read about Mohandas Gandhi"
    ]


def test_the_board_shows_them_too(client, user, colleague, handed_off):
    _watching(user)
    _own_chip(client, user)
    client.post(reverse("tasks:view-mode", args=["board"]))
    response = client.get(reverse("tasks:list"))
    cards = [t.description for c in response.context["columns"] for t in c["tasks"]]
    assert "Read about Mohandas Gandhi" in cards


def test_the_matter_tab_has_the_same_toggle(
    client, user, colleague, handed_off, matter
):
    client.post(reverse("matters:tasks-filter-user", args=[matter.id, user.id]))
    assert (
        _descriptions(client.get(reverse("matters:tasks-list", args=[matter.id]))) == []
    )
    client.post(reverse("matters:tasks-toggle-assigned", args=[matter.id]))
    assert _descriptions(
        client.get(reverse("matters:tasks-list", args=[matter.id]))
    ) == ["Read about Mohandas Gandhi"]


def test_restore_defaults_keeps_the_toggle(client, user, colleague, handed_off):
    _watching(user)
    client.get(reverse("tasks:filter-default"))
    user.refresh_from_db()
    assert user.show_assigned_tasks
    assert "Read about Mohandas Gandhi" in _descriptions(
        client.get(reverse("tasks:list"))
    )


def test_the_toolbar_button_reads_the_preference(client, user):
    html = client.get(reverse("tasks:list")).content.decode()
    assert "Show the tasks you assigned to others" in html
    client.post(reverse("tasks:toggle-assigned"))
    html = client.get(reverse("tasks:list")).content.decode()
    assert "Hide the tasks you assigned to others" in html
