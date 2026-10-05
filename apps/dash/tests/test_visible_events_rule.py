"""The Dash and the Plan chat take which events and tasks a user may see
from the apps' access helpers, not from rules of their own."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.calendar import access as calendar_access
from apps.calendar.models import Event
from apps.dash import agenda, views
from apps.tasks import access as tasks_access
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return CustomUser.objects.create(username="Ollie", email="ollie@example.com")


def _none_and_note(seen):
    def helper(queryset, user):
        seen.append(queryset.model)
        return queryset.none()

    return helper


def test_the_dash_calls_events_for_user(user, monkeypatch):
    Event.objects.create(
        description="Hearing", status="Pending", date=timezone.localdate()
    )
    seen = []
    monkeypatch.setattr(views, "events_for_user", _none_and_note(seen))
    events = views.dash_events_context(SimpleNamespace(user=user))["upcoming_events"]
    assert list(events) == []
    assert seen == [Event]


def test_the_plan_chat_calls_the_access_helpers(user, monkeypatch):
    today = timezone.localdate()
    Task.objects.create(
        user=user, description="Draft", status="Pending", date_due=today
    )
    Event.objects.create(
        description="Hearing", status="Pending", date=today + timedelta(days=1)
    )
    seen = []
    monkeypatch.setattr(tasks_access, "tasks_for_user", _none_and_note(seen))
    monkeypatch.setattr(calendar_access, "events_for_user", _none_and_note(seen))

    context = agenda._agenda_context(user)

    assert Task in seen and Event in seen
    assert "Draft" not in context
    assert "Hearing" not in context
