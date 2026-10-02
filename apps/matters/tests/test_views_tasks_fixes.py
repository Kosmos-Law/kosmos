"""Behaviour of a matter's Tasks tab: the Add Task status, quick add's length
limit, Restore Defaults in the filter dialog, and Bulk Update's checklist
guard."""

import json

import pytest
from django.urls import NoReverseMatch, reverse

from apps.checklists.models import Checklist, ChecklistItem
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def task(user, matter):
    return Task.objects.create(
        user=user, matter=matter, description="File the brief", status="Pending"
    )


# -----------------------------------------------------
# Add Task honours the form's Status
# -----------------------------------------------------
def test_add_honours_the_forms_status(client, user, matter):
    response = client.post(
        reverse("matters:tasks-add", args=[matter.id]),
        {
            "description": "Draft the motion",
            "user": user.id,
            "matter": matter.id,
            "importance": "4",
            "status": "On hold",
        },
    )
    assert response.status_code == 204
    assert Task.objects.get(description="Draft the motion").status == "On hold"


# -----------------------------------------------------
# quick add
# -----------------------------------------------------
def test_quick_add_refuses_a_line_over_the_limit(client, matter):
    response = client.post(
        reverse("matters:tasks-add-quick", args=[matter.id]),
        {"description": "x" * 201},
    )
    assert response.status_code == 422
    assert "HX-Trigger" not in response.headers
    toast = json.loads(response.headers["HX-Toast"])
    assert toast["type"] == "error"
    assert "200 characters" in toast["message"]
    assert not Task.objects.exists()


def test_quick_add_refuses_a_line_under_the_minimum(client, matter):
    response = client.post(
        reverse("matters:tasks-add-quick", args=[matter.id]), {"description": "abc"}
    )
    assert response.status_code == 422
    toast = json.loads(response.headers["HX-Toast"])
    assert toast["type"] == "error"
    assert "4 or more characters" in toast["message"]
    assert not Task.objects.exists()


def test_quick_add_at_the_limit_is_saved(client, matter):
    response = client.post(
        reverse("matters:tasks-add-quick", args=[matter.id]),
        {"description": "x" * 200},
    )
    assert response.status_code == 204
    assert Task.objects.get().matter == matter


# -----------------------------------------------------
# completing a task whose checklist is unfinished
# -----------------------------------------------------
@pytest.mark.parametrize(
    "name,args",
    [("matters:tasks-status", []), ("matters:tasks-set-status", ["complete"])],
)
def test_checklist_refusal_is_a_warning_toast(client, matter, task, name, args):
    checklist = Checklist.objects.create(task=task, name="Filing")
    ChecklistItem.objects.create(checklist=checklist, description="Proofread")
    response = client.post(reverse(name, args=[matter.id, task.id, *args]))
    assert response.status_code == 204
    toast = json.loads(response.headers["HX-Toast"])
    # "warning" is one of the four types the toast script knows.
    assert toast["type"] == "warning"
    assert "complete all checklist items" in toast["message"]
    task.refresh_from_db()
    assert task.status == "Pending"


# -----------------------------------------------------
# the focus control that set a field tasks do not have
# -----------------------------------------------------
def test_focus_route_is_gone(client, matter, task):
    with pytest.raises(NoReverseMatch):
        reverse("matters:tasks-focus", args=[matter.id, task.id, "Current"])
    url = f"/matters/{matter.id}/tasks/{task.id}/focus/Current"
    assert client.post(url).status_code == 404


# -----------------------------------------------------
# Restore Defaults
# -----------------------------------------------------
def test_restore_defaults_resets_this_tabs_filter_only(client, matter):
    firm_filter = {"status": ["Complete"], "filter_label": "all", "order_by": "status"}
    session = client.session
    session["tasks_filter"] = dict(firm_filter)
    session.save()

    url = reverse("matters:tasks-filter", args=[matter.id])
    client.post(url, {"status": ["Complete"], "importance": "7"})
    key = f"matter_tasks_filter_{matter.id}"
    assert client.session[key]["importance"] == "7"

    response = client.post(url, {"restore_defaults": "1"})
    # Stays on the tab: the list is refreshed in place, nothing redirects.
    assert response.status_code == 204
    assert response.headers["HX-Trigger"] == "tasksListChanged"
    assert client.session[key] == {"matter": matter.id}
    assert client.session["tasks_filter"] == firm_filter

    listing = client.get(reverse("matters:tasks-list", args=[matter.id]))
    assert listing.context["custom_filter_active"] is False


def test_restore_defaults_button_targets_the_tab_it_is_on(client, matter):
    matter_url = reverse("matters:tasks-filter", args=[matter.id])
    body = client.get(matter_url).content.decode()
    assert f'hx-post="{matter_url}"' in body
    assert "restore_defaults" in body
    assert reverse("tasks:filter-default") not in body

    # The firm-wide dialog keeps its own reset.
    body = client.get(reverse("tasks:filter")).content.decode()
    assert reverse("tasks:filter-default") in body
    assert "restore_defaults" not in body


# -----------------------------------------------------
# Bulk Update and unfinished checklists
# -----------------------------------------------------
def test_bulk_update_skips_tasks_with_unfinished_checklists(client, user, matter, task):
    blocked = Task.objects.create(
        user=user, matter=matter, description="Serve the brief", status="Pending"
    )
    checklist = Checklist.objects.create(task=blocked, name="Service")
    ChecklistItem.objects.create(checklist=checklist, description="Find the address")

    session = client.session
    session[f"selected_tasks_{matter.id}"] = [task.id, blocked.id]
    session.save()
    response = client.post(
        reverse("matters:tasks-bulk-update", args=[matter.id]),
        {"status": "Complete", "importance": "7"},
    )
    assert response.status_code == 204
    task.refresh_from_db()
    blocked.refresh_from_db()
    assert task.status == "Complete" and task.importance == 7
    assert blocked.status == "Pending" and blocked.importance == 4
    toast = json.loads(response.headers["HX-Toast"])
    assert toast["message"] == "1 task(s) skipped. Complete their checklists first."

    session = client.session
    session[f"selected_tasks_{matter.id}"] = [blocked.id]
    session.save()
    response = client.post(
        reverse("matters:tasks-bulk-set-status", args=[matter.id]),
        {"status": "Complete"},
    )
    toast = json.loads(response.headers["HX-Toast"])
    assert toast["message"] == "1 task(s) skipped. Complete their checklists first."
