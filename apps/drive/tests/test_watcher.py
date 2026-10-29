"""What the watcher records, which links it follows, and what a scan finds.

OCR itself is covered in test_ocr; here it is stubbed so the bookkeeping
can be checked quickly.
"""

import os

import pytest

from apps.drive import ocr, watcher
from apps.drive.models import FilesState, MatterFolder, PdfFile

from .conftest import blank_pdf_bytes, text_pdf_bytes

pytestmark = pytest.mark.django_db

SMITH = "Matters - Open/Smith v Jones"


@pytest.fixture
def fake_ocr(monkeypatch):
    """Stand in for OCRmyPDF: overwrite the file with a text PDF."""
    calls = []

    def run(path, jobs=None):
        calls.append(path)
        path.write_bytes(text_pdf_bytes())

    monkeypatch.setattr(ocr, "ocr_in_place", run)
    return calls


def test_a_pdf_with_text_is_recorded_and_left_alone(firm_root, fake_ocr):
    path = firm_root / SMITH / "brief.pdf"
    path.write_bytes(text_pdf_bytes())
    assert watcher.check_pdf(path) == "has_text"
    assert fake_ocr == []
    row = PdfFile.objects.get(path=f"{SMITH}/brief.pdf")
    assert row.has_text is True
    assert row.ocr_status == "none"


def test_a_pdf_without_text_is_ocrd_in_place(firm_root, fake_ocr):
    path = firm_root / SMITH / "scan.pdf"
    path.write_bytes(blank_pdf_bytes())
    assert watcher.check_pdf(path) == "ocr_done"
    assert fake_ocr == [path]
    row = PdfFile.objects.get(path=f"{SMITH}/scan.pdf")
    assert row.has_text is True
    assert row.ocr_status == "done"
    assert row.ocr_at is not None
    # The watcher's own write shows up as the version just recorded.
    assert watcher.check_pdf(path) == "unchanged"


def test_an_unchanged_pdf_is_not_reopened(firm_root, fake_ocr):
    path = firm_root / SMITH / "brief.pdf"
    path.write_bytes(text_pdf_bytes())
    watcher.check_pdf(path)
    assert watcher.check_pdf(path) == "unchanged"


def test_an_edited_pdf_is_checked_again(firm_root, fake_ocr):
    path = firm_root / SMITH / "doc.pdf"
    path.write_bytes(text_pdf_bytes())
    watcher.check_pdf(path)
    path.write_bytes(blank_pdf_bytes())
    os.utime(path, (1, 1))
    assert watcher.check_pdf(path) == "ocr_done"


def test_without_ocr_a_textless_pdf_is_left_pending(firm_root, fake_ocr):
    path = firm_root / SMITH / "scan.pdf"
    path.write_bytes(blank_pdf_bytes())
    assert watcher.check_pdf(path, run_ocr=False) == "pending"
    assert fake_ocr == []
    # A pending row is picked up again on the next pass.
    assert watcher.check_pdf(path) == "ocr_done"


def test_ocr_failures_stop_after_three_attempts(firm_root, monkeypatch):
    def fail(path, jobs=None):
        raise ocr.OcrError("tesseract exploded")

    monkeypatch.setattr(ocr, "ocr_in_place", fail)
    path = firm_root / SMITH / "scan.pdf"
    path.write_bytes(blank_pdf_bytes())
    for _ in range(watcher.MAX_ATTEMPTS):
        assert watcher.check_pdf(path) == "ocr_failed"
    row = PdfFile.objects.get(path=f"{SMITH}/scan.pdf")
    assert row.attempts == watcher.MAX_ATTEMPTS
    assert "tesseract exploded" in row.ocr_error
    # Settled: not tried again until the file changes.
    assert watcher.check_pdf(path) == "unchanged"
    assert PdfFile.objects.get(pk=row.pk).attempts == watcher.MAX_ATTEMPTS


def test_an_unreadable_pdf_is_recorded_as_failed(firm_root, fake_ocr):
    path = firm_root / SMITH / "broken.pdf"
    path.write_bytes(b"nope")
    assert watcher.check_pdf(path) == "unreadable"
    assert fake_ocr == []
    assert PdfFile.objects.get(path=f"{SMITH}/broken.pdf").ocr_status == "failed"
    empty = firm_root / SMITH / "empty.pdf"
    empty.write_bytes(b"")
    assert watcher.check_pdf(empty) == "unreadable"
    assert "empty" in PdfFile.objects.get(path=f"{SMITH}/empty.pdf").ocr_error


def test_a_deleted_pdf_loses_its_row(firm_root, fake_ocr):
    path = firm_root / SMITH / "brief.pdf"
    path.write_bytes(text_pdf_bytes())
    watcher.check_pdf(path)
    path.unlink()
    assert watcher.check_pdf(path) == "gone"
    assert not PdfFile.objects.filter(path=f"{SMITH}/brief.pdf").exists()


# -- links ---------------------------------------------------------------------


def test_refresh_links_flags_a_missing_folder_and_clears_it_when_back(
    firm_root, matter
):
    folder = MatterFolder.objects.create(matter=matter, path="Matters - Open/Gone")
    watcher.refresh_links()
    folder.refresh_from_db()
    assert folder.missing_since is not None
    (firm_root / "Matters - Open" / "Gone").mkdir()
    watcher.refresh_links()
    folder.refresh_from_db()
    assert folder.missing_since is None
    assert "Matters - Open/Gone" not in FilesState.get().unclaimed_folders


def test_follow_rename_moves_links_at_and_under_the_path(firm_root, matter, matter2):
    a = MatterFolder.objects.create(matter=matter, path="Matters - Open/Smith v Jones")
    b = MatterFolder.objects.create(
        matter=matter2, path="Matters - Open/Smith v Jones/Sub"
    )
    moved = watcher.follow_rename(
        "Matters - Open/Smith v Jones", "Matters - Pending/Smith v Jones"
    )
    assert moved == 2
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.path == "Matters - Pending/Smith v Jones"
    assert b.path == "Matters - Pending/Smith v Jones/Sub"


def test_a_rename_to_a_similar_prefix_is_not_followed(firm_root, matter):
    a = MatterFolder.objects.create(matter=matter, path="Matters - Open/Smith")
    assert watcher.follow_rename("Matters - Open/Smi", "Matters - Open/X") == 0
    a.refresh_from_db()
    assert a.path == "Matters - Open/Smith"


# -- the event reducer -------------------------------------------------------------


def test_events_are_debounced_and_renames_paired(firm_root, matter):
    MatterFolder.objects.create(matter=matter, path="Matters - Open/Smith v Jones")
    w = watcher.Watcher()
    w.handle(["IN_CLOSE_WRITE"], f"{SMITH}/scan.pdf", 0, now=10.0)
    w.handle(["IN_CLOSE_WRITE"], f"{SMITH}/scan.pdf", 0, now=11.0)  # touched again
    w.handle(["IN_CLOSE_WRITE"], f"{SMITH}/notes.odt", 0, now=11.0)  # not a PDF
    w.handle(["IN_CLOSE_WRITE"], ".dropbox.cache/tmp.pdf", 0, now=11.0)  # ignored
    w.handle(["IN_CLOSE_WRITE"], "Matters - Closed/2026/x/scan.pdf", 0, now=11.0)
    assert w.flush(now=12.0) == []  # still inside the debounce window
    assert w.flush(now=14.5) == [f"{SMITH}/scan.pdf"]
    assert w.flush(now=20.0) == []

    w.handle(["IN_MOVED_FROM", "IN_ISDIR"], SMITH, 77, now=30.0)
    w.handle(["IN_MOVED_TO", "IN_ISDIR"], "Matters - Open/Smith v. Jones", 77, now=30.1)
    assert (
        MatterFolder.objects.get(matter=matter).path == "Matters - Open/Smith v. Jones"
    )


def test_a_deleted_pdf_event_drops_the_row_and_pending_work(firm_root):
    PdfFile.objects.create(path=f"{SMITH}/old.pdf")
    w = watcher.Watcher()
    w.handle(["IN_CLOSE_WRITE"], f"{SMITH}/old.pdf", 0, now=1.0)
    w.handle(["IN_DELETE"], f"{SMITH}/old.pdf", 0, now=1.5)
    assert w.flush(now=10.0) == []
    assert not PdfFile.objects.filter(path=f"{SMITH}/old.pdf").exists()


# -- the full scan ---------------------------------------------------------------------


def test_scan_counts_every_pdf_and_prunes_rows_for_missing_files(
    firm_root, fake_ocr, matter
):
    (firm_root / SMITH / "brief.pdf").write_bytes(text_pdf_bytes())
    (firm_root / SMITH / "Evidence").mkdir()
    (firm_root / SMITH / "Evidence" / "scan.PDF").write_bytes(blank_pdf_bytes())
    (firm_root / ".dropbox.cache" / "partial.pdf").write_bytes(blank_pdf_bytes())
    closed = firm_root / "Matters - Closed" / "2020-2022" / "old.pdf"
    closed.write_bytes(blank_pdf_bytes())
    PdfFile.objects.create(path="Matters - Closed/2020-2022/seen-before.pdf")
    PdfFile.objects.create(path=f"{SMITH}/vanished.pdf")
    MatterFolder.objects.create(matter=matter, path=SMITH)

    stats = watcher.scan()

    assert stats == {"has_text": 1, "ocr_done": 1, "removed": 2, "empty_files": 0}
    assert closed.read_bytes() == blank_pdf_bytes()  # closed matters are left alone
    assert fake_ocr == [firm_root / SMITH / "Evidence" / "scan.PDF"]
    assert not PdfFile.objects.filter(path=f"{SMITH}/vanished.pdf").exists()
    state = FilesState.get()
    assert state.scanned_at is not None
    assert state.scan_stats == stats
    assert SMITH not in state.unclaimed_folders
    assert "Matters - Open/Doe v Roe" in state.unclaimed_folders


def test_scan_lists_empty_files_of_any_type_and_flags_new_ones(firm_root, fake_ocr):
    (firm_root / SMITH / "photo.jpg").write_bytes(b"")
    (firm_root / "Matters - Closed" / "2020-2022" / "old.pdf").write_bytes(b"")
    (firm_root / SMITH / "fine.pdf").write_bytes(text_pdf_bytes())

    stats = watcher.scan()
    state = FilesState.get()
    assert stats["empty_files"] == 2
    assert sorted(state.empty_files) == [
        "Matters - Closed/2020-2022/old.pdf",
        f"{SMITH}/photo.jpg",
    ]
    assert state.new_empty_files == []  # the first scan has nothing to compare

    (firm_root / SMITH / "late.odt").write_bytes(b"")
    watcher.scan()
    state = FilesState.get()
    assert state.new_empty_files == [f"{SMITH}/late.odt"]
    assert len(state.empty_files) == 3


def test_a_signed_pdf_is_not_retried(firm_root, monkeypatch):
    def refuse(path, jobs=None):
        raise ocr.OcrError("DigitalSignatureError: signed", permanent=True)

    monkeypatch.setattr(ocr, "ocr_in_place", refuse)
    signed = firm_root / SMITH / "signed.pdf"
    signed.write_bytes(blank_pdf_bytes())
    assert watcher.check_pdf(signed) == "ocr_failed"
    assert watcher.check_pdf(signed) == "unchanged"
    row = PdfFile.objects.get(path=f"{SMITH}/signed.pdf")
    assert row.attempts == watcher.MAX_ATTEMPTS and row.ocr_status == "failed"
