"""The Deadline Calculator answers a bad entry with a message, not a server
error, and its buttons show where it sits inside Add/Edit Event."""

from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

URL = "calendar:deadline-results"


def test_deadline_is_calculated(client):
    response = client.post(reverse(URL), {"initial_date": "2030-03-04", "days": "30"})

    assert response.status_code == 200
    assert b"2030-04-03" in response.content


@pytest.mark.parametrize("days", ["", "  ", "ten", "1.5"])
def test_unusable_days_show_a_message(client, days):
    response = client.post(reverse(URL), {"initial_date": "2030-03-04", "days": days})

    assert response.status_code == 200
    assert response.context["error"] == "Days must be a whole number."
    assert b"errorlist" in response.content


def test_missing_start_date_shows_a_message(client):
    response = client.post(reverse(URL), {"initial_date": "", "days": "30"})

    assert response.status_code == 200
    assert response.context["error"] == "Enter a start date."


def test_days_past_the_calendar_show_a_message(client):
    response = client.post(
        reverse(URL), {"initial_date": "2030-03-04", "days": "99999999"}
    )

    assert response.status_code == 200
    assert response.context["error"]


def test_only_the_stand_alone_dialog_hides_the_inline_buttons(client):
    """The rule that hides Hide/Calculate must name the stand-alone dialog,
    which has its own buttons in the footer. Scoped to any dialog, it also
    hid them in Add/Edit Event, which has no other way to run the
    calculator."""
    css = Path(settings.BASE_DIR, "static/css/apps/calendar.css").read_text()
    assert ".deadline-calculator-modal .deadline-calculator-actions" in css
    assert ".modal-content .deadline-calculator-actions" not in css

    modal = client.get(reverse("calendar:deadline-modal")).content.decode()
    event_form = client.get(reverse("calendar:add")).content.decode()
    assert "deadline-calculator-modal" in modal
    assert "deadline-calculator-modal" not in event_form
