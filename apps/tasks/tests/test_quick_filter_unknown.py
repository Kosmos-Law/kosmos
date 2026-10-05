"""An unknown date preset in the quick-filter address answers 404, as the
matter Tasks tab does, not a server error."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_unknown_quick_filter_is_404(client):
    url = reverse("tasks:filter-quick", args=["bogus"])
    assert client.get(url).status_code == 404


def test_known_quick_filter_still_applies(client):
    url = reverse("tasks:filter-quick", args=["today"])
    assert client.get(url).status_code == 200
    assert client.session["tasks_filter"]["filter_label"] == "today"
