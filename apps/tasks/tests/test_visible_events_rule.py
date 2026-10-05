"""The digest takes which events a user may see from the calendar's access
helper, not from a rule of its own."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.calendar.models import Event
from apps.tasks import digest

pytestmark = pytest.mark.django_db


def test_digest_events_come_through_events_for_user(user, monkeypatch):
    today = timezone.localdate()
    Event.objects.create(
        description="Hearing", status="Pending", date=today + timedelta(days=1)
    )
    seen = []

    def events_for_user(queryset, for_user):
        seen.append(for_user)
        return queryset.none()

    monkeypatch.setattr(digest, "events_for_user", events_for_user)
    mail.outbox.clear()

    # With the helper answering "no events" there is nothing to report.
    assert digest.send_digest_for_user(user) is False
    assert seen == [user]
    assert mail.outbox == []
