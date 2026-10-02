"""The board's move endpoints answer 400 to a body they cannot read, instead
of failing: ids that are not numbers, or JSON that is not an object."""

import json

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _post(client, name, payload):
    return client.post(
        reverse(name), json.dumps(payload), content_type="application/json"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"task_id": "abc"},
        {"task_id": None},
        {"task_id": [1]},
        {"task_id": 1.5},
        {"task_id": True},
        {"ordered_ids": ["abc"]},
        {"ordered_ids": [None]},
        {"ordered_ids": "12"},
        {"ordered_ids": {"a": 1}},
    ],
)
def test_board_move_refuses_ids_that_are_not_numbers(client, task, change):
    payload = {"task_id": task.id, "status_slug": "on-hold", "ordered_ids": [task.id]}
    response = _post(client, "tasks:board-move", payload | change)
    assert response.status_code == 400
    assert response.json() == {"ok": False, "message": "Invalid request."}
    # Nothing is saved from a move that is refused.
    task.refresh_from_db()
    assert task.status == "Pending"
    assert task.custom_order is None


@pytest.mark.parametrize("name", ["tasks:board-move", "tasks:board-bulk-move"])
@pytest.mark.parametrize("payload", [[1, 2], "text", 7, None])
def test_body_that_is_not_an_object_is_refused(client, name, payload):
    assert _post(client, name, payload).status_code == 400


def test_numeric_strings_are_still_accepted(client, task):
    payload = {
        "task_id": str(task.id),
        "status_slug": "on-hold",
        "ordered_ids": [str(task.id)],
    }
    assert _post(client, "tasks:board-move", payload).status_code == 200
    task.refresh_from_db()
    assert task.status == "On hold"
    assert task.custom_order == 0
