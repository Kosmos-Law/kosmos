from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.calendar.models import Event
from apps.dash.views import dash_events_context
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


def _event(**kwargs):
    return Event.objects.create(description="Site visit", **kwargs)


def _request(**user_fields):
    """A stand-in request for a user who, by default, sees every matter."""
    user = CustomUser.objects.create(username="Ollie", **user_fields)
    return SimpleNamespace(user=user)


def test_past_due_pending_events_stay_visible():
    today = timezone.localdate()
    past = _event(status="Pending", date=today - timedelta(days=1))
    upcoming = _event(status="Pending", date=today + timedelta(days=3))

    events = list(dash_events_context(_request())["upcoming_events"])
    assert events == [past, upcoming]  # past-due sorts first


def test_resolved_and_undated_events_hidden():
    today = timezone.localdate()
    _event(status="Complete", date=today - timedelta(days=1))
    _event(status="Missed", date=today - timedelta(days=2))
    _event(status="Pending", date=None)

    assert list(dash_events_context(_request())["upcoming_events"]) == []


def test_context_dates():
    today = timezone.localdate()
    context = dash_events_context(_request())
    assert context["today"] == today
    assert context["tomorrow"] == today + timedelta(days=1)
    assert context["yesterday"] == today - timedelta(days=1)


def test_events_on_unassigned_matters_are_hidden_from_a_restricted_user():
    today = timezone.localdate()
    request = _request(perm_all_matters=False)
    mine = Matter.objects.create(name="Assigned Matter", status="Open")
    mine.members.add(request.user)
    theirs = Matter.objects.create(name="Unassigned Matter", status="Open")
    on_mine = _event(status="Pending", date=today, matter=mine)
    _event(status="Pending", date=today + timedelta(days=1), matter=theirs)
    firm_wide = _event(status="Pending", date=today + timedelta(days=2))

    events = list(dash_events_context(request)["upcoming_events"])

    assert events == [on_mine, firm_wide]
