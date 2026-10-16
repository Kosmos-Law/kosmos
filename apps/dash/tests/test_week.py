from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.calendar.models import Event
from apps.dash import week
from apps.matters.models import Matter
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db

# A Thursday; its week runs Sunday Oct 11 to Saturday Oct 17
TODAY = date(2026, 10, 15)
FIRST, LAST = date(2026, 10, 11), date(2026, 10, 17)


@pytest.fixture
def user():
    return CustomUser.objects.create(username="Ollie", email="ollie@example.com")


def _event(**kwargs):
    kwargs.setdefault("status", "Pending")
    kwargs.setdefault("description", "Site visit")
    return Event.objects.create(**kwargs)


def _task(user, **kwargs):
    kwargs.setdefault("status", "Pending")
    kwargs.setdefault("description", "Draft motion")
    return Task.objects.create(user=user, **kwargs)


def _feed(user, first=FIRST, last=LAST, tasks=False):
    return week.week_feed(user, first, last, TODAY, tasks=tasks)


def _client(user):
    """A client signed in as the user, past the day's first visit to the
    dash (which would redirect the feed's request there)."""
    user.last_dash_check = timezone.localdate()
    user.save(update_fields=["last_dash_check"])
    client = Client()
    client.force_login(user)
    return client


def _ids(entries):
    return {e["id"] for e in entries}


def test_pending_events_in_the_week_are_fed_as_the_calendar_feeds_them(user):
    timed = _event(date=TODAY, start_time=time(14, 30))
    all_day = _event(date=TODAY)
    _event(date=TODAY, status="Complete")
    _event(date=date(2026, 10, 18))  # next week

    entries = {e["id"]: e for e in _feed(user)}
    assert set(entries) == {str(timed.id), str(all_day.id)}
    assert entries[str(timed.id)]["start"] == "2026-10-15T14:30:00"
    assert entries[str(timed.id)]["allDay"] is False
    assert entries[str(all_day.id)]["allDay"] is True


def test_an_event_that_began_before_the_week_is_fed(user):
    trial = _event(date=date(2026, 10, 9), end_date=date(2026, 10, 12))
    [entry] = _feed(user)
    assert entry["id"] == str(trial.id)
    assert entry["end"] == "2026-10-13"


def test_events_on_unassigned_matters_are_hidden_from_a_restricted_user():
    user = CustomUser.objects.create(username="Rita", perm_all_matters=False)
    mine = Matter.objects.create(name="Assigned Matter", status="Open")
    mine.members.add(user)
    theirs = Matter.objects.create(name="Unassigned Matter", status="Open")
    on_mine = _event(date=TODAY, matter=mine)
    _event(date=TODAY, matter=theirs)
    firm_wide = _event(date=TODAY, start_time=time(10))

    assert _ids(_feed(user)) == {str(on_mine.id), str(firm_wide.id)}


def test_the_title_is_the_calendars(user):
    matter = Matter.objects.create(name="Smith v. Jones", status="Open")
    _event(date=TODAY, matter=matter, description="Hearing")
    assert _feed(user)[0]["title"].startswith("Smith v. Jones - Hearing")


def test_the_toggle_starts_on(user):
    assert week.show_tasks(SimpleNamespace(session={}))
    assert not week.show_tasks(SimpleNamespace(session={week.SHOW_TASKS_KEY: False}))


def test_tasks_stay_off_the_week_with_the_toggle_off(user):
    _task(user, date_due=TODAY)
    assert _feed(user) == []


def test_open_tasks_are_fed_on_their_days(user):
    task = _task(user, date_due=TODAY)
    _task(user, date_due=TODAY, status="Complete")
    _task(CustomUser.objects.create(username="other"), date_due=TODAY)

    [entry] = _feed(user, tasks=True)
    assert entry["id"] == f"task-{task.id}"
    assert entry["start"] == "2026-10-15"
    assert entry["extendedProps"] == {"kind": "task", "task_id": task.id}


def test_the_week_holding_today_gathers_overdue_tasks_on_today(user):
    old = _task(user, date_due=date(2026, 9, 2))
    monday = _task(user, date_due=date(2026, 10, 12))

    entries = {e["id"]: e for e in _feed(user, tasks=True)}
    gathered = entries[f"task-{old.id}"]
    assert gathered["start"] == "2026-10-15"
    assert gathered["extendedProps"]["overdue"] is True
    assert gathered["extendedProps"]["due_label"] == "Sep 2"
    assert "fc-event-overdue" in gathered["className"]
    # a task due earlier this week stays on its day; it is not overdue
    # from before the week
    assert entries[f"task-{monday.id}"]["start"] == "2026-10-12"
    assert "overdue" not in entries[f"task-{monday.id}"]["extendedProps"]

    # another week shows only its own tasks, on their days
    [entry] = _feed(user, date(2026, 8, 30), date(2026, 9, 5), tasks=True)
    assert entry["id"] == f"task-{old.id}"
    assert entry["start"] == "2026-09-02"


def test_past_three_tasks_the_rest_fold_into_more_tasks(user):
    old = _task(user, date_due=date(2026, 9, 2), description="Z overdue")
    for n in range(4):
        _task(user, date_due=TODAY, description=f"Task {n}")

    entries = _feed(user, tasks=True)
    shown = [e for e in entries if e["extendedProps"]["kind"] == "task"]
    # the overdue task leads, then today's by title
    assert [e["title"] for e in shown] == ["Z overdue", "Task 0", "Task 1"]
    assert shown[0]["id"] == f"task-{old.id}"
    [fold] = [e for e in entries if e["extendedProps"]["kind"] == "more-tasks"]
    assert fold["title"] == "2 more tasks"
    assert fold["start"] == "2026-10-15"
    assert fold["editable"] is False


def test_the_feed_view_reads_fullcalendars_range(user):
    client = _client(user)
    today = timezone.localdate()
    _event(date=today, description="Mediation")
    _event(date=today + timedelta(days=30), description="Later")
    start = today - timedelta(days=1)
    response = client.get(
        reverse("dash:week-feed"),
        {"start": f"{start}T00:00:00-04:00", "end": f"{today + timedelta(days=1)}"},
    )
    assert response.status_code == 200
    assert [e["title"] for e in response.json()] == ["Mediation"]
    response = client.get(reverse("dash:week-feed"), {"start": "nope", "end": ""})
    assert response.status_code == 400


def test_the_toggle_remembers_and_the_feed_follows(user):
    client = _client(user)
    today = timezone.localdate()
    _task(user, date_due=today, description="File reply")
    params = {"start": str(today), "end": str(today + timedelta(days=1))}

    response = client.post(reverse("dash:week-tasks", args=["off"]))
    assert response.status_code == 204
    assert client.session[week.SHOW_TASKS_KEY] is False
    assert client.get(reverse("dash:week-feed"), params).json() == []

    client.post(reverse("dash:week-tasks", args=["on"]))
    assert client.session[week.SHOW_TASKS_KEY] is True
    feed = client.get(reverse("dash:week-feed"), params).json()
    assert [e["title"] for e in feed] == ["File reply"]

    response = client.post(reverse("dash:week-tasks", args=["maybe"]))
    assert response.status_code == 400


def test_the_dash_draws_the_week_as_a_calendar(user):
    client = Client()
    client.force_login(user)
    response = client.get(reverse("dash:index"))
    # The template formatter lays the x-data object over several lines
    content = " ".join(response.content.decode().split())
    assert "eventsCalendar({week: true" in content
    assert reverse("dash:week-feed") in content
    assert "tasks: true" in content
