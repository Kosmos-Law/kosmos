"""Tests for draft-link services: creation, staleness refresh."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.drafts import services
from apps.drafts.models import DraftLink

pytestmark = pytest.mark.django_db


def in_matter_folder(monkeypatch, *file_ids):
    """Fake the matter's Drive folder listing: these files are in it."""
    monkeypatch.setattr(
        services,
        "list_matter_odt_files",
        lambda matter: [
            {"id": fid, "name": f"{fid}.odt", "path": "", "modifiedTime": ""}
            for fid in file_ids
        ],
    )


@pytest.fixture
def drive(monkeypatch):
    """Fake the Drive fetch: records calls, returns canned text. The
    ``name`` entry is what Drive currently calls the file."""
    calls = {"count": 0, "name": "motion.odt"}

    def fake_fetch(drive_file_id):
        calls["count"] += 1
        return calls["name"], f"TEXT {calls['count']}"

    monkeypatch.setattr(services, "_fetch_drive_text", fake_fetch)
    in_matter_folder(monkeypatch, "file1", "file2")
    return calls


def test_create_link_snapshots_text(conversation, drive):
    link = services.create_link(conversation, "file1")
    assert link.name == "motion.odt"
    assert link.doc_text == "TEXT 1"
    assert link.doc_text_at is not None
    assert conversation.draft_link == link


def test_create_link_refuses_second_link(conversation, drive):
    services.create_link(conversation, "file1")
    conversation.refresh_from_db()
    with pytest.raises(services.DraftError, match="already has"):
        services.create_link(conversation, "file2")
    assert DraftLink.objects.count() == 1


def test_non_odt_rejected(conversation, monkeypatch):
    monkeypatch.setattr(services.google, "check_credentials", lambda: True)
    monkeypatch.setattr(services.google, "build_service", lambda: object())

    class FakeFiles:
        def get(self, **kwargs):
            return self

        def execute(self):
            return {"name": "brief.docx"}

    monkeypatch.setattr(services.google, "_download", lambda service, meta: b"bytes")
    service = type("S", (), {"files": lambda self: FakeFiles()})()
    monkeypatch.setattr(services.google, "build_service", lambda: service)
    in_matter_folder(monkeypatch, "file1")
    with pytest.raises(services.DraftError, match="odt"):
        services.create_link(conversation, "file1")


def test_unreadable_odt_is_a_draft_error(conversation, monkeypatch):
    """A file pandoc cannot convert is reported like any other link
    failure, not left to become a server error."""

    class FakeFiles:
        def get(self, **kwargs):
            return self

        def execute(self):
            return {"name": "motion.odt"}

    service = type("S", (), {"files": lambda self: FakeFiles()})()
    monkeypatch.setattr(services.google, "check_credentials", lambda: True)
    monkeypatch.setattr(services.google, "build_service", lambda: service)
    monkeypatch.setattr(services.google, "_download", lambda service, meta: b"bytes")

    def boom(content, ext):
        raise services.convert.ConversionError("pandoc failed for .odt file: bad zip")

    monkeypatch.setattr(services.convert, "to_markdown", boom)
    in_matter_folder(monkeypatch, "file1")
    with pytest.raises(services.DraftError, match="could not be read"):
        services.create_link(conversation, "file1")
    assert not DraftLink.objects.exists()


def test_refresh_if_stale_refetches(link, drive):
    link.doc_text_at = timezone.now() - timedelta(minutes=10)
    link.save()
    services.refresh_if_stale(link)
    link.refresh_from_db()
    assert link.doc_text == "TEXT 1"


def test_refresh_follows_a_rename_in_drive(link, drive, user, matter):
    """The companion pairs a document with its link by file name, so a
    stale name leaves the renamed file unable to connect."""
    from apps.case.ai.models import Conversation

    sibling = DraftLink.objects.create(
        conversation=Conversation.objects.create(matter=matter, title="B", user=user),
        drive_file_id=link.drive_file_id,
        name="motion.odt",
    )
    drive["name"] = "motion-v2.odt"
    link.doc_text_at = timezone.now() - timedelta(minutes=10)
    link.save()

    services.refresh_if_stale(link)
    link.refresh_from_db()
    sibling.refresh_from_db()
    assert link.name == "motion-v2.odt"
    assert sibling.name == "motion-v2.odt"


def test_refresh_skipped_when_fresh(link, drive):
    services.refresh_if_stale(link)
    assert drive["count"] == 0


def test_refresh_skipped_when_companion_active(link, drive):
    link.doc_text_at = timezone.now() - timedelta(minutes=10)
    link.companion_seen = timezone.now()
    link.save()
    services.refresh_if_stale(link)
    assert drive["count"] == 0


def test_refresh_fails_soft(link, monkeypatch):
    link.doc_text_at = timezone.now() - timedelta(minutes=10)
    link.save()

    def boom(drive_file_id):
        raise services.DraftError("Drive is down")

    monkeypatch.setattr(services, "_fetch_drive_text", boom)
    services.refresh_if_stale(link)
    link.refresh_from_db()
    assert link.doc_text == "# MOTION\n\nSome text."
