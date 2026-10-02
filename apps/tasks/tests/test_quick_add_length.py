"""Quick add holds a description to the task form's limits (4 to 200
characters) and says so when it refuses one."""

import json

import pytest
from django.urls import reverse

from apps.tasks.models import Task

pytestmark = pytest.mark.django_db

TOO_LONG = "Call " + "x" * 200


def _toast(response):
    return json.loads(response.headers["HX-Toast"])


def test_long_line_is_refused_with_a_message(client):
    response = client.post(reverse("tasks:add-quick"), {"description": TOO_LONG})
    # Not a success: the input clears only after a successful request, so
    # what was typed stays there to be shortened.
    assert response.status_code == 422
    assert "HX-Trigger" not in response.headers
    toast = _toast(response)
    assert toast["type"] == "error"
    assert "200 characters" in toast["message"]
    assert not Task.objects.exists()


def test_limit_is_on_the_description_not_the_matter_prefix(client, matter):
    line = "Sample - " + "x" * 200
    response = client.post(reverse("tasks:add-quick"), {"description": line})
    assert response.status_code == 204
    task = Task.objects.get()
    assert len(task.description) == 200
    assert task.matter == matter


@pytest.mark.parametrize("line", ["abc", "Sample - abc", "  ab  "])
def test_short_line_is_refused_with_a_message(client, matter, line):
    response = client.post(reverse("tasks:add-quick"), {"description": line})
    assert response.status_code == 422
    assert "HX-Trigger" not in response.headers
    toast = _toast(response)
    assert toast["type"] == "error"
    assert "4 or more characters" in toast["message"]
    assert not Task.objects.exists()


def test_four_characters_is_enough(client):
    response = client.post(reverse("tasks:add-quick"), {"description": "Call"})
    assert response.status_code == 204
    assert Task.objects.get().description == "Call"


def test_empty_line_stays_a_silent_no_op(client):
    response = client.post(reverse("tasks:add-quick"), {"description": ""})
    assert response.status_code == 204
    assert "HX-Toast" not in response.headers
    assert not Task.objects.exists()


def test_ai_description_over_the_limit_is_refused(client, monkeypatch):
    monkeypatch.setattr(
        "apps.tasks.views._quick_add_ai_entry",
        lambda request: {"description": TOO_LONG, "matter": None},
    )
    response = client.post(reverse("tasks:add-quick"), {"description": "anything"})
    assert response.status_code == 422
    assert "200 characters" in _toast(response)["message"]
    assert not Task.objects.exists()
