"""An event deleted on Google and kept here says so on screen: on the list
rows (firm and matter) and above the Edit Event form."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.calendar.models import Event

pytestmark = pytest.mark.django_db

NOTE = "Not on Google Calendar"


@pytest.fixture
def detached(user, matter):
    return Event.objects.create(
        user=user,
        matter=matter,
        date="2030-01-01",
        description="Kept after Google deletion",
        status="Pending",
        google_id=None,
        google_synced_at=timezone.now(),
    )


@pytest.fixture
def never_pushed(user, matter):
    return Event.objects.create(
        user=user,
        matter=matter,
        date="2030-01-02",
        description="Never on Google",
        status="Pending",
    )


def test_the_firm_list_marks_a_detached_event(client, detached, never_pushed):
    client.post(reverse("calendar:view-mode", args=["list"]))
    html = client.get(reverse("calendar:list")).content.decode()
    assert html.count(NOTE) == 1
    assert html.index("Kept after Google deletion") < html.index(NOTE)


def test_the_matter_list_marks_a_detached_event(client, matter, detached, never_pushed):
    client.post(reverse("matters:events-view-mode", args=[matter.id, "list"]))
    html = client.get(reverse("matters:events", args=[matter.id])).content.decode()
    assert html.count(NOTE) == 1
    assert html.index("Kept after Google deletion") < html.index(NOTE)


def test_the_edit_form_says_it(client, detached, never_pushed):
    assert (
        NOTE
        in client.get(reverse("calendar:edit", args=[detached.id])).content.decode()
    )
    assert (
        NOTE
        not in client.get(
            reverse("calendar:edit", args=[never_pushed.id])
        ).content.decode()
    )
