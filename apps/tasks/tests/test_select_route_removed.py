"""The old /tasks address, which only redirected to the index, is gone; the
one link that used it (the Admin link on a matterless row) goes to the
index itself."""

import pytest
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse

from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


def test_select_route_is_gone(client):
    with pytest.raises(NoReverseMatch):
        reverse("tasks:select")
    assert client.get("/tasks").status_code == 404


def test_admin_link_goes_to_the_index(user):
    task = Task(user=user, description="Order toner", status="Pending")
    html = render_to_string("tasks/matter.html", {"task": task})
    assert f'href="{reverse("tasks:index")}"' in html
