"""An event with no party (one made on Google Calendar) shows an empty
Party cell on the matter Events tab, not the word None."""

import pytest
from django.urls import reverse

from apps.calendar.models import Event

pytestmark = pytest.mark.django_db


def test_missing_party_renders_empty(client, user, matter):
    Event.objects.create(
        user=user,
        matter=matter,
        party=None,
        date="2026-01-01",
        status="Pending",
        description="Imported from Google",
    )
    response = client.get(reverse("matters:events", args=[matter.id]))
    assert response.status_code == 200
    assert "Imported from Google" in response.content.decode()
    assert '<td class="party">None</td>' not in response.content.decode()
    assert '<td class="party"></td>' in response.content.decode()
