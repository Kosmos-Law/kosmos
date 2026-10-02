"""Whose tasks and events the daily digest email carries."""

from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.calendar.models import Event
from apps.tasks.digest import send_digest_for_user
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def records(user, matter, other_matter):
    today = timezone.localdate()
    for label, on in (("own", matter), ("other", other_matter), ("firm", None)):
        Task.objects.create(
            user=user,
            matter=on,
            description=f"Task on {label} matter",
            status="Pending",
            date_due=today,
        )
        Event.objects.create(
            matter=on,
            description=f"Event on {label} matter",
            status="Pending",
            date=today + timedelta(days=1),
        )


def _digest(user):
    mail.outbox.clear()
    assert send_digest_for_user(user) is True
    return mail.outbox[0].body


def test_restricted_user_gets_own_and_matterless_records(restricted, records):
    body = _digest(restricted)
    for label in ("own", "firm"):
        assert f"Task on {label} matter" in body
        assert f"Event on {label} matter" in body
    assert "Task on other matter" not in body
    assert "Event on other matter" not in body
    assert "Unassigned Matter" not in body


def test_admin_limited_to_assigned_matters_gets_everything(restricted, records):
    restricted.role = "ADMIN"
    restricted.save()
    body = _digest(restricted)
    for label in ("own", "other", "firm"):
        assert f"Task on {label} matter" in body
        assert f"Event on {label} matter" in body


def test_restricted_user_with_only_matterless_records_still_gets_a_digest(
    restricted, user
):
    Task.objects.create(
        user=user,
        description="Order more toner",
        status="Pending",
        date_due=timezone.localdate(),
    )
    assert "Order more toner" in _digest(restricted)
