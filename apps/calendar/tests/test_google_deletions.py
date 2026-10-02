"""An event deleted on Google.

The deletion removes the event in Kosmos only when Kosmos holds nothing
Google did not: the event is Pending and has no edits waiting to be pushed.
A Complete or Missed event, or one with unpushed edits, stays. It is cut
loose from Google instead, and nothing sends it back there as a new event.
"""

from datetime import date

import pytest

import apps.calendar.google as google
import apps.calendar.sync as sync
from apps.calendar.models import Event

pytestmark = pytest.mark.django_db


class FakeGoogle:
    """Stands in for the Calendar API client; keeps what was sent."""

    def __init__(self):
        self.sent = []

    def events(self):
        return self

    def insert(self, calendarId, body):
        self.sent.append(body)
        return self

    def update(self, calendarId, eventId, body):
        self.sent.append(body)
        return self

    def execute(self):
        return {"id": "google-1"}


@pytest.fixture
def remote(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(google, "check_credentials", lambda: True)
    monkeypatch.setattr(google, "build_service", lambda: fake)
    return fake


def _synced(matter, remote, status="Pending"):
    """An event on Google and in step with it, in the given status."""
    event = Event.objects.create(
        matter=matter,
        date=date(2030, 3, 4),
        description="Hearing",
        status="Pending",
    )
    assert sync.push_event(event) == "ok"
    if status != "Pending":
        # Marked done in Kosmos. A status other than Pending is never pushed,
        # so the event is in step again as far as the sync is concerned.
        event.status = status
        event.save()
        Event.objects.filter(pk=event.pk).update(
            google_synced_at=Event.objects.get(pk=event.pk).updated_at
        )
    event.refresh_from_db()
    remote.sent.clear()
    return event


def _delete_on_google(event):
    return google._process_google_event({"id": "google-1", "status": "cancelled"})


def _detached(event):
    event.refresh_from_db()
    return event.google_id is None and event.detached_from_google


def test_pending_event_in_step_is_deleted(remote, matter):
    event = _synced(matter, remote)

    assert _delete_on_google(event) == "deleted"
    assert not Event.objects.filter(pk=event.pk).exists()


@pytest.mark.parametrize("status", ["Complete", "Missed"])
def test_finished_event_is_kept_and_detached(remote, matter, status):
    event = _synced(matter, remote, status=status)

    assert _delete_on_google(event) == "detached"

    assert _detached(event)
    assert event.status == status
    assert event.description == "Hearing"


def test_finished_event_with_unpushed_edits_is_kept(remote, matter):
    event = _synced(matter, remote)
    event.status = "Complete"
    event.save()

    assert _delete_on_google(event) == "detached"
    assert _detached(event)


def test_pending_event_with_unpushed_edits_is_kept_and_detached(remote, matter):
    event = _synced(matter, remote)
    event.description = "Hearing, moved to courtroom 4"
    event.save()

    assert _delete_on_google(event) == "detached"

    assert _detached(event)
    assert event.status == "Pending"
    assert event.description == "Hearing, moved to courtroom 4"


def test_detaching_leaves_the_edit_time_alone(remote, matter):
    event = _synced(matter, remote, status="Complete")
    edited = event.updated_at

    _delete_on_google(event)

    event.refresh_from_db()
    assert event.updated_at == edited


def test_detached_event_is_not_pushed_back_by_the_next_sync(remote, matter):
    event = _synced(matter, remote)
    event.description = "Hearing, moved to courtroom 4"
    event.save()
    _delete_on_google(event)

    summary = sync.reconcile()

    assert summary == {"pushed": 0, "deleted": 0, "failed": 0}
    assert remote.sent == []
    assert _detached(event)


def test_detached_event_is_not_pushed_when_edited_later(remote, matter):
    event = _synced(matter, remote)
    event.description = "Hearing, moved to courtroom 4"
    event.save()
    _delete_on_google(event)
    event.refresh_from_db()

    event.description = "Hearing, moved again"
    event.save()

    assert sync.push_event(event) == "skipped"
    assert sync.reconcile()["pushed"] == 0
    assert remote.sent == []
    assert _detached(event)


def test_detached_finished_event_is_not_pushed_when_reopened(remote, matter):
    event = _synced(matter, remote, status="Complete")
    _delete_on_google(event)
    event.refresh_from_db()

    event.status = "Pending"
    event.save()

    assert sync.push_event(event) == "skipped"
    assert sync.reconcile()["pushed"] == 0
    assert remote.sent == []


def test_detached_event_is_not_matched_again(remote, matter):
    event = _synced(matter, remote, status="Complete")
    _delete_on_google(event)

    assert _delete_on_google(event) == "skipped"
    assert Event.objects.filter(pk=event.pk).exists()


def test_event_never_pushed_is_still_pushed(remote, matter):
    """The detached state must not catch an event that is only new."""
    event = Event.objects.create(
        matter=matter, date=date(2030, 3, 4), description="New", status="Pending"
    )

    assert not event.detached_from_google
    assert sync.reconcile()["pushed"] == 1
    assert len(remote.sent) == 1
