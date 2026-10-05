"""The matter Tasks tab has no "focus" dimension: Task has no such field,
so neither the filter route nor the tab's context carries one."""

import pytest
from django.urls import NoReverseMatch, reverse

pytestmark = pytest.mark.django_db


def test_filter_focus_route_is_gone(client, matter):
    with pytest.raises(NoReverseMatch):
        reverse("matters:tasks-filter-focus", args=[matter.id, "Current"])
    assert (
        client.get(f"/matters/{matter.id}/tasks/filter-focus/Current").status_code
        == 404
    )


def test_the_tab_context_has_no_focus(client, matter):
    response = client.get(reverse("matters:tasks-list", args=[matter.id]))
    assert response.status_code == 200
    assert "focus" not in response.context
