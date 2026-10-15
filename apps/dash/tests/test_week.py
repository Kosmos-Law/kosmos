from datetime import date, time

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.calendar.models import Event
from apps.dash import week
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db

# A Thursday; its week runs Sunday Oct 11 to Saturday Oct 17
TODAY = date(2026, 10, 15)


@pytest.fixture
def user():
    return CustomUser.objects.create(username="Ollie", email="ollie@example.com")


def _event(**kwargs):
    kwargs.setdefault("status", "Pending")
    kwargs.setdefault("description", "Site visit")
    return Event.objects.create(**kwargs)


def _days(user, week_of=None):
    return week.week_context(user, week_of=week_of, today=TODAY)["week"]


def test_the_week_runs_sunday_to_saturday_with_today_marked(user):
    days = _days(user)
    assert [d.date for d in days] == [date(2026, 10, d) for d in range(11, 18)]
    assert [d.label for d in days][:2] == ["Sun", "Mon"]
    assert [d.is_today for d in days].index(True) == 4


def test_pending_events_land_on_their_days_all_day_first(user):
    late = _event(date=TODAY, start_time=time(14, 30))
    early = _event(date=TODAY, start_time=time(9))
    all_day = _event(date=TODAY)
    _event(date=TODAY, status="Complete")
    _event(date=date(2026, 10, 18))  # next week

    today = _days(user)[4]
    assert today.entries == [all_day, early, late]
    assert [e.time_label for e in today.entries] == ["", "9a", "2:30p"]


def test_an_event_over_several_days_shows_on_each(user):
    trial = _event(date=date(2026, 10, 9), end_date=date(2026, 10, 12))
    days = _days(user)
    assert [d.entries for d in days[:3]] == [[trial], [trial], []]


def test_a_crowded_day_folds_the_rest_into_more(user):
    for _ in range(week.DAY_LIMIT + 2):
        _event(date=TODAY)
    today = _days(user)[4]
    assert len(today.entries) == week.DAY_LIMIT
    assert today.more == 2


def test_the_chevrons_and_span(user):
    context = week.week_context(user, week_of=date(2026, 10, 28), today=TODAY)
    assert context["week_first"] == date(2026, 10, 25)
    assert context["week_range"] == "Oct 25 – 31"
    assert context["week_previous"] == date(2026, 10, 18)
    assert context["week_next"] == date(2026, 11, 1)
    assert not context["week_is_current"]
    assert week.week_range(date(2026, 11, 29), TODAY) == "Nov 29 – Dec 5"
    assert week.week_range(date(2026, 12, 27), TODAY) == "Dec 27 – Jan 2, 2027"


def test_events_on_unassigned_matters_are_hidden_from_a_restricted_user():
    user = CustomUser.objects.create(username="Rita", perm_all_matters=False)
    mine = Matter.objects.create(name="Assigned Matter", status="Open")
    mine.members.add(user)
    theirs = Matter.objects.create(name="Unassigned Matter", status="Open")
    on_mine = _event(date=TODAY, matter=mine)
    _event(date=TODAY, matter=theirs)
    firm_wide = _event(date=TODAY, start_time=time(10))

    assert _days(user)[4].entries == [on_mine, firm_wide]


def test_the_title_is_the_calendars(user):
    matter = Matter.objects.create(name="Smith v. Jones", status="Open")
    event = _event(date=TODAY, matter=matter, description="Hearing")
    event.assignees.add(
        CustomUser.objects.create(username="al", first_name="Ada", last_name="Lee")
    )
    assert (
        _days(user)[4].entries[0].calendar_title.startswith("Smith v. Jones - Hearing")
    )


def test_the_section_view_steps_to_the_week_asked_for(user):
    client = Client()
    client.force_login(user)
    _event(date=date(2026, 11, 3), description="Mediation")
    response = client.get(
        reverse("dash:events-section"), {"start": "2026-11-03"}, HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 200
    assert b"Mediation" in response.content
    # a bad date falls back to this week
    response = client.get(
        reverse("dash:events-section"), {"start": "nope"}, HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 200
