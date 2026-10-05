"""An event with no party (one made on Google Calendar) shows an empty
Party cell on the Calendar list, not the word None."""

import pytest
from django.urls import reverse

from apps.calendar.models import Event

pytestmark = pytest.mark.django_db


def test_missing_party_renders_empty(client, user):
    Event.objects.create(
        user=user,
        party=None,
        date="2030-01-01",
        status="Pending",
        description="Imported from Google",
    )
    client.post(reverse("calendar:view-mode", args=["list"]))
    html = client.get(reverse("calendar:list")).content.decode()
    assert "Imported from Google" in html
    assert '<td class="party">None</td>' not in html
    assert '<td class="party"></td>' in html
