"""The event lists: the firm Calendar's and a matter's Events tab."""

import pytest
from django.urls import reverse

from apps.calendar.models import Event

pytestmark = pytest.mark.django_db


def test_matter_events_tab_has_no_filter_button(client, matter):
    body = client.get(reverse("matters:events", args=[matter.id])).content.decode()

    assert reverse("calendar:filter") not in body


def test_duration_reads_as_one_word(client, matter):
    Event.objects.create(
        matter=matter,
        date="2030-03-04",
        start_time="09:00",
        end_time="10:30",
        description="Ninety minutes",
        status="Pending",
    )
    client.post(reverse("calendar:view-mode", args=["list"]))

    firm_list = client.get(reverse("calendar:list")).content.decode()
    client.post(reverse("matters:events-view-mode", args=[matter.id, "list"]))
    matter_list = client.get(reverse("matters:events", args=[matter.id]))

    assert "1.5 hrs" in firm_list
    assert "1.5 hrs" in matter_list.content.decode()
