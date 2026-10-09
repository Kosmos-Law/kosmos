"""The calendar's JSON API, for another app to overlay Kosmos's events:
token auth, the range, what each event carries, and who sees what."""

from datetime import time

import pytest
from django.test import Client
from django.urls import reverse

from apps.calendar.models import Event
from apps.drafts.models import CompanionToken

pytestmark = pytest.mark.django_db

MARCH = {"start": "2030-03-01", "end": "2030-03-31"}


@pytest.fixture
def api(user):
    api = Client()
    api.defaults["HTTP_X_KOSMOS_TOKEN"] = CompanionToken.for_user(user).key
    return api


@pytest.fixture
def events(user, matter):
    return {
        "timed": Event.objects.create(
            user=user,
            matter=matter,
            date="2030-03-04",
            start_time=time(9, 0),
            end_time=time(10, 30),
            description="Hearing",
            location="Courtroom 3",
            status="Pending",
        ),
        "all_day": Event.objects.create(
            user=user, date="2030-03-05", description="Filing deadline"
        ),
        "outside": Event.objects.create(
            user=user, date="2030-04-01", description="Next month"
        ),
    }


def test_the_api_needs_a_token(user):
    assert Client().get(reverse("calendar:api-events"), MARCH).status_code == 401
    bad = Client()
    bad.defaults["HTTP_X_KOSMOS_TOKEN"] = "not-a-key"
    assert bad.get(reverse("calendar:api-events"), MARCH).status_code == 401


def test_the_events_in_the_range_come_back_as_rows(api, events, settings):
    response = api.get(reverse("calendar:api-events"), MARCH)

    assert response.status_code == 200
    data = response.json()
    assert data["time_zone"] == settings.TIME_ZONE
    rows = {row["id"]: row for row in data["events"]}
    assert set(rows) == {events["timed"].id, events["all_day"].id}
    timed = rows[events["timed"].id]
    assert timed["title"] == "Sample Test Matter - Hearing"
    assert (timed["date"], timed["start_time"], timed["end_time"]) == (
        "2030-03-04",
        "09:00:00",
        "10:30:00",
    )
    assert timed["all_day"] is False
    assert timed["matter"] == "Sample Test Matter"
    assert timed["location"] == "Courtroom 3"
    assert timed["url"].endswith(f"/events/{events['timed'].id}/edit")
    all_day = rows[events["all_day"].id]
    assert all_day["all_day"] is True and all_day["start_time"] is None


def test_a_bad_range_is_refused(api):
    assert api.get(reverse("calendar:api-events"), {"start": "soon"}).status_code == 400
    assert (
        api.get(
            reverse("calendar:api-events"), {"start": "2030-03-31", "end": "2030-03-01"}
        ).status_code
        == 400
    )
    assert (
        api.get(
            reverse("calendar:api-events"), {"start": "2030-01-01", "end": "2032-01-01"}
        ).status_code
        == 400
    )


def test_a_user_sees_only_the_matters_they_may(user, matter, events):
    from apps.accounts.models import CustomUser

    limited = CustomUser.objects.create(
        username="lim", email="lim@example.com", perm_all_matters=False
    )
    api = Client()
    api.defaults["HTTP_X_KOSMOS_TOKEN"] = CompanionToken.for_user(limited).key

    rows = api.get(reverse("calendar:api-events"), MARCH).json()["events"]

    assert [row["id"] for row in rows] == [events["all_day"].id]


def test_a_deactivated_user_is_refused(user, api, events):
    user.is_active = False
    user.save()

    assert api.get(reverse("calendar:api-events"), MARCH).status_code == 401
