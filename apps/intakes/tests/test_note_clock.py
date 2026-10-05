"""A note's date and time are stamped in the firm's time zone, not the
server's wall clock: the views used naive datetime.now() for the time while
the date came from timezone.localdate(), so on a UTC server an evening call
could land under tomorrow's date with a time hours off."""

import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from django.test import Client
from django.utils import timezone

from apps.intakes.models import Intake, Note

from .test_api import SEAM_KEY

pytestmark = pytest.mark.django_db

# 01:30 UTC on the 6th is 20:30 on the 5th in New York (winter, UTC-5).
LATE_EVENING = datetime(2026, 1, 6, 1, 30, tzinfo=UTC)
NEW_YORK = ZoneInfo("America/New_York")


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch, settings):
    settings.KOSMOS_SEAM_KEY = SEAM_KEY
    monkeypatch.setattr(timezone, "now", lambda: LATE_EVENING)
    with timezone.override(NEW_YORK):
        yield


def _seam_post(url, payload):
    return Client(headers={"X-Seam-Key": SEAM_KEY}).post(
        url, data=json.dumps(payload), content_type="application/json"
    )


def test_an_inquiry_note_is_stamped_in_the_firms_time_zone():
    response = _seam_post(
        "/api/receive-inquiry/",
        {
            "full_name": "Jane Roe",
            "phone_number": "4045550100",
            "email": "jane@example.com",
            "summary": "My neighbor moved a fence onto my land.",
        },
    )

    note = Note.objects.get(intake_id=response.json()["intake_id"])
    assert str(note.date) == "2026-01-05"
    assert note.time.strftime("%H:%M") == "20:30"


def test_a_client_form_note_is_stamped_in_the_firms_time_zone():
    response = _seam_post(
        "/api/receive-intake/",
        {
            "full_name": "Jane Roe",
            "phone_number": "4045550100",
            "email": "jane@example.com",
            "report": "CLIENT INTAKE REPORT",
        },
    )

    body = response.json()
    assert str(Intake.objects.get(id=body["intake_id"]).date) == "2026-01-05"
    note = Note.objects.get(id=body["note_id"])
    assert str(note.date) == "2026-01-05"
    assert note.time.strftime("%H:%M") == "20:30"


def test_the_add_note_form_opens_at_the_firms_time(client):
    intake = Intake.objects.create(name="Jane Roe", status="Open")

    response = client.get(f"/intakes/{intake.id}/add-note")

    form = response.context["form"]
    assert form.initial["date"] == "2026-01-05"
    assert form.initial["time"].strftime("%H:%M") == "20:30"
