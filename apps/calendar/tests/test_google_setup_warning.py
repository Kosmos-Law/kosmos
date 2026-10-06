"""The event form and save toasts on a firm without (or half-way into)
Google Calendar.

A firm that never connected Google sees no warning at all. A connected
calendar with no CALENDAR_ID is a half-finished setup: the form warns, and
a failed save names that cause instead of asking for a reconnect.
"""

import logging

import pytest

import apps.calendar.google as google

pytestmark = pytest.mark.django_db


@pytest.fixture
def not_connected(monkeypatch):
    monkeypatch.setattr(google, "check_credentials", lambda: False)


@pytest.fixture
def connected_no_calendar(monkeypatch):
    monkeypatch.setattr(google, "check_credentials", lambda: True)
    monkeypatch.setattr(google, "CALENDAR_ID", "")


@pytest.fixture
def connected(monkeypatch):
    monkeypatch.setattr(google, "check_credentials", lambda: True)
    monkeypatch.setattr(google, "CALENDAR_ID", "firm@group.calendar.google.com")


def test_never_connected_form_has_no_warning(client, not_connected):
    body = client.get("/events/add").content.decode()

    assert 'class="warn"' not in body
    assert "Not connected to a Google calendar" not in body


def test_connected_without_calendar_id_form_warns(client, connected_no_calendar):
    body = client.get("/events/add").content.decode()

    assert 'class="warn"' in body
    assert "CALENDAR_ID" in body


def test_fully_connected_form_has_no_warning(client, connected):
    body = client.get("/events/add").content.decode()

    assert 'class="warn"' not in body


def test_edit_form_follows_the_same_rule(client, event, connected_no_calendar):
    body = client.get(f"/events/{event.id}/edit/test").content.decode()

    assert "CALENDAR_ID" in body


def _failing_service():
    raise RuntimeError("calendarId is required")


def test_save_without_calendar_id_names_the_cause(
    client, event_data, connected_no_calendar, monkeypatch
):
    monkeypatch.setattr(google, "build_service", _failing_service)

    response = client.post("/events/add", event_data)

    assert response.status_code == 204
    toast = response["HX-Toast"]
    assert "CALENDAR_ID" in toast
    assert "Reconnect" not in toast


def test_failed_save_when_set_up_still_suggests_reconnecting(
    client, event_data, connected, monkeypatch
):
    monkeypatch.setattr(google, "build_service", _failing_service)

    response = client.post("/events/add", event_data)

    assert "Reconnect it in Settings" in response["HX-Toast"]


def test_save_when_never_connected_has_no_toast(client, event_data, not_connected):
    response = client.post("/events/add", event_data)

    assert response.status_code == 204
    assert "HX-Toast" not in response


def test_scheduled_pull_when_not_connected_is_not_an_error(not_connected, caplog):
    with caplog.at_level(logging.DEBUG, logger="apps.calendar.google"):
        google.sync_from_google()

    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_scheduled_pull_without_calendar_id_is_an_error(connected_no_calendar, caplog):
    with caplog.at_level(logging.DEBUG, logger="apps.calendar.google"):
        google.sync_from_google()

    assert any(
        r.levelno == logging.ERROR and "CALENDAR_ID" in r.getMessage()
        for r in caplog.records
    )
