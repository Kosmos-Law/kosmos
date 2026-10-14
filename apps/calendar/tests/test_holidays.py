"""The calendar can show US federal holidays beside its events, and the
deadline calculator counts them as court holidays."""

from datetime import date

import pytest
from django.urls import reverse

from apps.calendar import holidays

pytestmark = pytest.mark.django_db

JULY = {"start": "2027-06-27", "end": "2027-08-07"}


def _toolbar(client):
    return client.get(reverse("calendar:overlays")).content.decode()


def _feed(client, params):
    return {
        row["id"]: row for row in client.get(reverse("calendar:feed"), params).json()
    }


def test_holidays_are_off_by_default(client):
    assert not any(key.startswith("holiday-") for key in _feed(client, JULY))
    assert client.get(reverse("calendar:index")).context["show_holidays"] is False


def test_the_toggle(client):
    response = client.post(reverse("calendar:show-holidays", args=["on"]))

    assert response.status_code == 204
    assert response["HX-Trigger"] == "eventsChanged"
    assert client.get(reverse("calendar:index")).context["show_holidays"] is True
    assert reverse("calendar:show-holidays", args=["off"]) in _toolbar(client)

    client.post(reverse("calendar:show-holidays", args=["off"]))
    assert client.get(reverse("calendar:index")).context["show_holidays"] is False
    assert (
        client.post(reverse("calendar:show-holidays", args=["maybe"])).status_code
        == 400
    )


def test_the_holidays_in_the_range_show(client):
    client.post(reverse("calendar:show-holidays", args=["on"]))

    feed = _feed(client, JULY)
    shown = {key for key in feed if key.startswith("holiday-")}

    # Independence Day 2027 is a Sunday, so the Monday is observed too
    assert shown == {"holiday-2027-07-04", "holiday-2027-07-05"}
    fourth = feed["holiday-2027-07-04"]
    assert fourth["title"] == "Independence Day"
    assert fourth["allDay"] is True
    assert fourth["start"] == "2027-07-04"
    assert fourth["className"] == "fc-event-holiday"
    assert fourth["editable"] is False
    assert fourth["extendedProps"] == {"kind": "holiday"}
    assert feed["holiday-2027-07-05"]["title"] == "Independence Day (observed)"


def test_the_matter_tab_shows_no_overlays(client, matter):
    client.post(reverse("calendar:show-holidays", args=["on"]))

    feed = client.get(reverse("calendar:feed-matter", args=[matter.id]), JULY).json()

    assert not any(row["id"].startswith("holiday-") for row in feed)


def test_a_range_over_the_new_year_has_both_years():
    days = [row["start"] for row in holidays.feed(date(2026, 12, 20), date(2027, 1, 5))]

    assert days == ["2026-12-25", "2027-01-01"]


def test_the_toolbar_offers_the_toggle(client):
    assert reverse("calendar:show-holidays", args=["on"]) in _toolbar(client)
    assert "Show holidays" in _toolbar(client)


# --- court days ------------------------------------------------------------


def test_court_days():
    assert holidays.is_court_day(date(2026, 11, 25))
    assert not holidays.is_court_day(date(2026, 11, 26))  # Thanksgiving
    assert not holidays.is_court_day(date(2026, 11, 28))  # Saturday
    assert holidays.next_court_day(date(2026, 11, 26)) == date(2026, 11, 27)
    assert holidays.next_court_day(date(2026, 7, 3)) == date(2026, 7, 6)
    assert holidays.name_of(date(2026, 7, 3)) == "Independence Day (observed)"


def test_a_deadline_on_a_holiday_runs_to_the_next_court_day(client):
    # 2026-11-01 + 25 days is Thanksgiving
    response = client.post(
        reverse("calendar:deadline-results"),
        {"initial_date": "2026-11-01", "days": "25"},
    )

    results = response.context["results"]
    assert results["holiday"] == "Thanksgiving Day"
    assert results["next_workday"] == date(2026, 11, 27)
    assert b"Next Court Day" in response.content


def test_a_deadline_on_a_saturday_runs_to_monday(client):
    response = client.post(
        reverse("calendar:deadline-results"),
        {"initial_date": "2030-03-04", "days": "5"},
    )

    results = response.context["results"]
    assert results["deadline_weekday"] == "Saturday"
    assert results["holiday"] is None
    assert results["next_workday"] == date(2030, 3, 11)


def test_a_deadline_on_a_court_day_stands(client):
    response = client.post(
        reverse("calendar:deadline-results"),
        {"initial_date": "2030-03-04", "days": "1"},
    )

    assert response.context["results"]["next_workday"] is None
