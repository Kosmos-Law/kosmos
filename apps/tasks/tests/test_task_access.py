"""Who may see and change tasks on the firm-wide Tasks tab.

A user limited to assigned matters reaches the tasks on those matters and the
tasks on no matter, and nothing else: not in the list or the board, not by a
task's id, not through a selection, and not through the matter a form offers.
"""

import json

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.tasks.ai import _matter_lines
from apps.tasks.models import Task, TaskNote

pytestmark = pytest.mark.django_db

ALL_TASKS_FILTER = {
    "status": ["Pending", "In progress", "On hold", "Complete"],
    "order_by": "date_due",
    "filter_label": "all",
}


def _task(user, matter, description, **extra):
    return Task.objects.create(
        user=user, matter=matter, description=description, status="Pending", **extra
    )


@pytest.fixture
def own_task(user, matter):
    return _task(user, matter, "Task on my matter")


@pytest.fixture
def other_task(user, other_matter):
    return _task(user, other_matter, "Task on their matter")


@pytest.fixture
def admin_task(user):
    return _task(user, None, "Task on no matter")


def _show_everything(client):
    session = client.session
    session["tasks_filter"] = dict(ALL_TASKS_FILTER)
    session.save()


def _select(client, *task_ids):
    session = client.session
    session["selected_tasks"] = list(task_ids)
    session.save()


# -----------------------------------------------------
# the list and the board
# -----------------------------------------------------
def test_list_shows_own_and_matterless_tasks_only(
    restricted_client, own_task, other_task, admin_task
):
    _show_everything(restricted_client)
    body = restricted_client.get(reverse("tasks:list")).content.decode()
    assert own_task.description in body
    assert admin_task.description in body
    assert other_task.description not in body
    assert other_task.matter.name not in body


def test_board_shows_own_and_matterless_tasks_only(
    restricted_client, own_task, other_task, admin_task
):
    _show_everything(restricted_client)
    restricted_client.post(reverse("tasks:view-mode", args=["board"]))
    body = restricted_client.get(reverse("tasks:list")).content.decode()
    assert own_task.description in body
    assert admin_task.description in body
    assert other_task.description not in body


def test_unrestricted_user_still_sees_every_task(client, own_task, other_task):
    _show_everything(client)
    body = client.get(reverse("tasks:list")).content.decode()
    assert own_task.description in body
    assert other_task.description in body


def test_admin_limited_to_assigned_matters_sees_every_task(
    restricted, restricted_client, other_task
):
    # update(), not save(): saving this stale object would undo the day's
    # dash check-in and redirect the next request.
    CustomUser.objects.filter(pk=restricted.pk).update(role="ADMIN")
    _show_everything(restricted_client)
    body = restricted_client.get(reverse("tasks:list")).content.decode()
    assert other_task.description in body


def test_filter_cannot_be_pointed_at_another_matter(
    restricted_client, other_matter, other_task
):
    url = reverse("tasks:filter-matter", args=[other_matter.id])
    assert restricted_client.post(url).status_code == 403

    # A matter id left in the session from before is dropped, not named.
    session = restricted_client.session
    session["tasks_filter"] = {**ALL_TASKS_FILTER, "matter": other_matter.id}
    session.save()
    response = restricted_client.get(reverse("tasks:list"))
    assert other_matter.name not in response.content.decode()
    assert response.context["matter_id"] is None


# -----------------------------------------------------
# a task reached by its id
# -----------------------------------------------------
BY_ID_GETS = ["tasks:edit", "tasks:detail", "tasks:detail-notes", "tasks:add-note"]


@pytest.mark.parametrize("name", BY_ID_GETS + ["tasks:date"])
def test_other_matters_task_cannot_be_opened(restricted_client, other_task, name):
    response = restricted_client.get(reverse(name, args=[other_task.id]))
    assert response.status_code == 403


@pytest.mark.parametrize("name", BY_ID_GETS + ["tasks:date"])
def test_matterless_and_own_tasks_can_be_opened(
    restricted_client, own_task, admin_task, name
):
    for task in (own_task, admin_task):
        response = restricted_client.get(reverse(name, args=[task.id]))
        assert response.status_code == 200


def test_other_matters_task_cannot_be_changed(
    restricted, restricted_client, other_task
):
    task_id = other_task.id
    posts = [
        (reverse("tasks:edit", args=[task_id]), {"description": "Taken over"}),
        (reverse("tasks:delete", args=[task_id]), {}),
        (reverse("tasks:task-status", args=[task_id]), {}),
        (reverse("tasks:set-status", args=[task_id, "complete"]), {}),
        (reverse("tasks:task-importance", args=[task_id, 7]), {}),
        (reverse("tasks:task-user", args=[task_id, restricted.id]), {}),
        (reverse("tasks:task-matter", args=[task_id, 0]), {}),
        (reverse("tasks:date", args=[task_id]), {"date_due": "2030-01-01"}),
        (reverse("tasks:add-note", args=[task_id]), {"details": "Seen it"}),
        (reverse("tasks:toggle-select", args=[task_id]), {}),
    ]
    for url, data in posts:
        assert restricted_client.post(url, data).status_code == 403, url

    other_task.refresh_from_db()
    assert other_task.description == "Task on their matter"
    assert other_task.status == "Pending"
    assert other_task.importance == 4
    assert other_task.user != restricted
    assert other_task.matter_id is not None
    assert other_task.date_due is None
    assert not other_task.notes.exists()


def test_notes_on_another_matters_task_are_out_of_reach(
    user, restricted_client, other_task
):
    note = TaskNote.objects.create(task=other_task, user=user, details="Privileged")
    edit = reverse("tasks:edit-note", args=[note.id])
    assert restricted_client.get(edit).status_code == 403
    assert restricted_client.post(edit, {"details": "Changed"}).status_code == 403
    delete = reverse("tasks:delete-note", args=[note.id])
    assert restricted_client.post(delete).status_code == 403
    note.refresh_from_db()
    assert note.details == "Privileged"


def test_task_cannot_be_moved_onto_another_matter(
    restricted_client, own_task, other_matter
):
    url = reverse("tasks:task-matter", args=[own_task.id, other_matter.id])
    assert restricted_client.post(url).status_code == 403
    own_task.refresh_from_db()
    assert own_task.matter_id != other_matter.id


# -----------------------------------------------------
# bulk actions: the selection is re-filtered on the server
# -----------------------------------------------------
def test_bulk_delete_leaves_other_matters_task(restricted_client, own_task, other_task):
    _select(restricted_client, own_task.id, other_task.id)
    response = restricted_client.post(reverse("tasks:bulk-delete"))
    assert response.status_code == 204
    assert not Task.objects.filter(pk=own_task.id).exists()
    assert Task.objects.filter(pk=other_task.id).exists()


@pytest.mark.parametrize(
    "name,data,field,untouched",
    [
        ("tasks:bulk-set-status", {"status": "On hold"}, "status", "Pending"),
        ("tasks:bulk-set-status", {"status": "Complete"}, "status", "Pending"),
        ("tasks:bulk-set-importance", {"importance": "7"}, "importance", 4),
        ("tasks:bulk-set-due-date", {"date_due": "2030-01-01"}, "date_due", None),
        ("tasks:bulk-update", {"status": "On hold"}, "status", "Pending"),
    ],
)
def test_bulk_change_leaves_other_matters_task(
    restricted_client, own_task, other_task, name, data, field, untouched
):
    _select(restricted_client, own_task.id, other_task.id)
    assert restricted_client.post(reverse(name), data).status_code == 204
    other_task.refresh_from_db()
    own_task.refresh_from_db()
    assert getattr(other_task, field) == untouched
    assert getattr(own_task, field) != untouched


def test_bulk_reassign_and_clear_date_leave_other_matters_task(
    restricted, restricted_client, own_task, other_task
):
    Task.objects.filter(pk__in=[own_task.id, other_task.id]).update(
        date_due="2030-01-01"
    )
    _select(restricted_client, own_task.id, other_task.id)
    restricted_client.post(reverse("tasks:bulk-set-user"), {"user": restricted.id})
    _select(restricted_client, own_task.id, other_task.id)
    restricted_client.post(reverse("tasks:bulk-clear-due-date"))
    other_task.refresh_from_db()
    own_task.refresh_from_db()
    assert own_task.user == restricted and own_task.date_due is None
    assert other_task.user != restricted and other_task.date_due is not None


def test_board_move_refuses_and_reorder_skips_other_matters_task(
    restricted_client, own_task, other_task
):
    def move(task_id, ordered):
        return restricted_client.post(
            reverse("tasks:board-move"),
            json.dumps(
                {"task_id": task_id, "status_slug": "on-hold", "ordered_ids": ordered}
            ),
            content_type="application/json",
        )

    assert move(other_task.id, [other_task.id]).status_code == 403
    assert move(own_task.id, [other_task.id, own_task.id]).status_code == 200
    other_task.refresh_from_db()
    own_task.refresh_from_db()
    assert other_task.status == "Pending" and other_task.custom_order is None
    assert own_task.status == "On hold" and own_task.custom_order == 1


def test_board_bulk_move_leaves_other_matters_task(
    restricted_client, own_task, other_task
):
    _select(restricted_client, own_task.id, other_task.id)
    response = restricted_client.post(
        reverse("tasks:board-bulk-move"),
        json.dumps({"status_slug": "on-hold"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    other_task.refresh_from_db()
    own_task.refresh_from_db()
    assert other_task.status == "Pending"
    assert own_task.status == "On hold"


# -----------------------------------------------------
# the matters a form offers and accepts
# -----------------------------------------------------
def _matter_choice_ids(form):
    return {m.id for m in form.fields["matter"].queryset}


def test_add_form_offers_only_own_matters(restricted_client, matter, other_matter):
    response = restricted_client.get(reverse("tasks:add"))
    assert _matter_choice_ids(response.context["form"]) == {matter.id}
    assert other_matter.name not in response.content.decode()


def test_add_refuses_a_matter_that_is_not_offered(
    restricted, restricted_client, other_matter
):
    response = restricted_client.post(
        reverse("tasks:add"),
        {
            "description": "Planted task",
            "user": restricted.id,
            "matter": other_matter.id,
            "importance": "4",
            "status": "Pending",
        },
    )
    assert response.status_code == 200
    assert "matter" in response.context["form"].errors
    assert not Task.objects.filter(description="Planted task").exists()


def test_edit_form_offers_only_own_matters_and_refuses_others(
    restricted, restricted_client, own_task, matter, other_matter
):
    url = reverse("tasks:edit", args=[own_task.id])
    response = restricted_client.get(url)
    assert _matter_choice_ids(response.context["form"]) == {matter.id}

    response = restricted_client.post(
        url,
        {
            "description": own_task.description,
            "user": restricted.id,
            "matter": other_matter.id,
            "importance": "4",
            "status": "Pending",
        },
    )
    assert response.status_code == 200
    own_task.refresh_from_db()
    assert own_task.matter_id == matter.id


def test_edit_form_keeps_a_closed_matter_the_task_is_on(client, task, matter):
    matter.status = "Closed"
    matter.save()
    response = client.get(reverse("tasks:edit", args=[task.id]))
    assert matter.id in _matter_choice_ids(response.context["form"])


def test_filter_dialog_offers_only_own_matters(restricted_client, matter, other_matter):
    response = restricted_client.get(reverse("tasks:filter"))
    offered = {m.id for m in response.context["filter"].form.fields["matter"].queryset}
    assert offered == {matter.id}
    assert other_matter.name not in response.content.decode()


def test_list_context_offers_only_own_matters(restricted_client, matter, other_matter):
    response = restricted_client.get(reverse("tasks:list"))
    assert {m.id for m in response.context["matters"]} == {matter.id}


def test_bulk_update_offers_and_accepts_only_own_matters(
    restricted_client, admin_task, matter, other_matter
):
    _select(restricted_client, admin_task.id)
    response = restricted_client.get(reverse("tasks:bulk-update"))
    assert _matter_choice_ids(response.context["form"]) == {matter.id}

    response = restricted_client.post(
        reverse("tasks:bulk-update"), {"matter": other_matter.id}
    )
    assert response.status_code == 200
    assert "matter" in response.context["form"].errors
    admin_task.refresh_from_db()
    assert admin_task.matter_id is None


# -----------------------------------------------------
# quick add
# -----------------------------------------------------
def test_quick_add_prefix_does_not_reach_another_matter(
    restricted_client, other_matter
):
    response = restricted_client.post(
        reverse("tasks:add-quick"), {"description": "Unassigned - call the clerk"}
    )
    assert response.status_code == 204
    task = Task.objects.get(description="Call the clerk")
    assert task.matter is None
    assert other_matter.name not in response.headers.get("HX-Toast", "")


def test_quick_add_prefix_still_reaches_own_matter(restricted_client, matter):
    restricted_client.post(
        reverse("tasks:add-quick"), {"description": "Sample - call the clerk"}
    )
    assert Task.objects.get(description="Call the clerk").matter == matter


def test_ai_quick_add_does_not_reach_another_matter(
    restricted, restricted_client, matter, other_matter, monkeypatch
):
    monkeypatch.setattr(
        "apps.tasks.views._quick_add_ai_entry",
        lambda request: {
            "description": "Call the clerk",
            "matter": other_matter.name,
            "user": None,
            "due": None,
            "importance": None,
        },
    )
    restricted_client.post(reverse("tasks:add-quick"), {"description": "anything"})
    assert Task.objects.get(description="Call the clerk").matter is None

    lines = _matter_lines(restricted)
    assert matter.name in lines
    assert other_matter.name not in lines


def test_quick_add_ignores_a_filter_matter_that_is_not_the_users(
    restricted_client, other_matter
):
    session = restricted_client.session
    session["tasks_filter"] = {**ALL_TASKS_FILTER, "matter": other_matter.id}
    session.save()
    restricted_client.post(
        reverse("tasks:add-quick"), {"description": "Call the clerk"}
    )
    assert Task.objects.get(description="Call the clerk").matter is None


def test_restricted_fixture_is_not_an_admin(restricted):
    # The tests above mean nothing if the fixture can see every matter.
    assert not restricted.is_admin
    assert not CustomUser.objects.get(pk=restricted.pk).perm_all_matters
