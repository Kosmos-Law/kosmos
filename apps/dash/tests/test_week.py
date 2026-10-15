from datetime import date, time
from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.calendar.models import Event
from apps.dash import week
from apps.matters.models import Matter
from apps.tasks.models import Task

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
    assert _entries(today) == [("event", e.id) for e in (all_day, early, late)]
    assert [e.time_label for e in today.entries] == ["", "9a", "2:30p"]


def test_an_event_over_several_days_shows_on_each(user):
    trial = _event(date=date(2026, 10, 9), end_date=date(2026, 10, 12))
    days = _days(user)
    assert [_entries(d) for d in days[:3]] == [[("event", trial.id)]] * 2 + [[]]


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

    assert _entries(_days(user)[4]) == [("event", on_mine.id), ("event", firm_wide.id)]


def test_the_title_is_the_calendars(user):
    matter = Matter.objects.create(name="Smith v. Jones", status="Open")
    event = _event(date=TODAY, matter=matter, description="Hearing")
    event.assignees.add(
        CustomUser.objects.create(username="al", first_name="Ada", last_name="Lee")
    )
    assert _days(user)[4].entries[0].title.startswith("Smith v. Jones - Hearing")


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


def _task(user, **kwargs):
    kwargs.setdefault("status", "Pending")
    kwargs.setdefault("description", "Draft motion")
    return Task.objects.create(user=user, **kwargs)


def _entries(day):
    return [(e.kind, e.id) for e in day.entries]


def test_the_toggle_starts_on(user):
    assert week.show_tasks(SimpleNamespace(session={}))
    assert not week.show_tasks(SimpleNamespace(session={week.SHOW_TASKS_KEY: False}))


def test_tasks_stay_off_the_week_with_the_toggle_off(user):
    _task(user, date_due=TODAY)
    assert _days(user)[4].entries == []


def test_open_tasks_land_on_their_days_between_all_day_and_timed_events(user):
    timed = _event(date=TODAY, start_time=time(9))
    all_day = _event(date=TODAY)
    task = _task(user, date_due=TODAY)
    _task(user, date_due=TODAY, status="Complete")
    _task(CustomUser.objects.create(username="other"), date_due=TODAY)

    days = week.week_context(user, today=TODAY, tasks=True)["week"]
    assert _entries(days[4]) == [
        ("event", all_day.id),
        ("task", task.id),
        ("event", timed.id),
    ]


def test_this_week_gathers_overdue_tasks_on_today(user):
    old = _task(user, date_due=date(2026, 9, 2))
    monday = _task(user, date_due=date(2026, 10, 12))

    days = week.week_context(user, today=TODAY, tasks=True)["week"]
    today = days[4]
    assert _entries(today) == [("task", old.id)]
    assert today.entries[0].overdue
    assert today.entries[0].time_label == "Sep 2"
    # a task due earlier this week stays on its day; it is not overdue
    # from before the week
    assert _entries(days[1]) == [("task", monday.id)]

    # another week shows only its own tasks
    later = week.week_context(user, week_of=date(2026, 9, 2), today=TODAY, tasks=True)
    assert _entries(later["week"][3]) == [("task", old.id)]
    assert not later["week"][3].entries[0].overdue


def test_the_toggle_remembers_and_redraws_the_week_in_view(user):
    client = Client()
    client.force_login(user)
    _task(user, date_due=date(2026, 11, 3), description="File reply")
    url = reverse("dash:week-tasks", args=["on"])
    response = client.post(url, {"start": "2026-11-03"}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert b"File reply" in response.content
    assert client.session[week.SHOW_TASKS_KEY] is True

    response = client.post(
        reverse("dash:week-tasks", args=["off"]),
        {"start": "2026-11-03"},
        HTTP_HX_REQUEST="true",
    )
    assert b"File reply" not in response.content
    assert client.session[week.SHOW_TASKS_KEY] is False
    response = client.post(
        reverse("dash:week-tasks", args=["maybe"]), HTTP_HX_REQUEST="true"
    )
    assert response.status_code == 400


def test_past_three_tasks_the_rest_fold_into_more_tasks(user):
    event = _event(date=TODAY, start_time=time(15))
    for n in range(5):
        _task(user, date_due=TODAY, description=f"Task {n}")

    today = week.week_context(user, today=TODAY, tasks=True)["week"][4]
    assert [e.kind for e in today.entries] == ["task"] * 3 + ["event"]
    assert today.entries[-1].id == event.id
    assert today.more_tasks == 2
    assert today.more == 0
