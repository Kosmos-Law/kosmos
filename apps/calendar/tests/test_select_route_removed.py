"""The old /events/select address, which only redirected to the calendar
index and had no caller, is gone."""

import pytest
from django.urls import NoReverseMatch, reverse

pytestmark = pytest.mark.django_db


def test_select_route_is_gone(client):
    with pytest.raises(NoReverseMatch):
        reverse("calendar:select")
    assert client.get("/events/select").status_code == 404
