"""The Dash takes which events a user may see from the calendar's access
helper, not from a rule of its own."""

from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.calendar.models import Event
from apps.dash import views

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
