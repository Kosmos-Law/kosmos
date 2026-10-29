"""Watch the Firm tree: OCR new PDFs, follow renamed folders, list free ones.

Two entry points. ``scan()`` walks the whole tree once (start-up, nightly,
``manage.py watch_files --scan``). ``Watcher().run()`` is the long-running
loop under the ``files-watcher`` service: inotify on the tree, each event
debounced for a few seconds (Dropbox writes a file and then touches it),
PDFs handed to one worker thread so a long OCR never blocks the event
queue, and a heartbeat the Settings page reads.

Links are never removed here. A linked folder that moves is followed by
its rename cookie; one that vanishes is flagged ``missing_since`` and
left for a person to resolve.
"""

import logging
import os
import queue
import threading
import time
from collections import Counter
from pathlib import Path

from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from . import ocr, text, tree
from .models import FilesState, MatterFolder, PdfFile

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 3.0
HEARTBEAT_SECONDS = 30.0
SCAN_INTERVAL_SECONDS = 24 * 3600
MOVE_COOKIE_TTL = 5.0
# OCR attempts on one version of a file before it is left as failed.
MAX_ATTEMPTS = 3
# Zero-byte paths kept on the state row (the count is always exact).
EMPTY_FILES_KEPT = 2000

PDF_SUFFIX = ".pdf"


def rel(path: Path) -> str:
    return path.relative_to(tree.root()).as_posix()


# --------------------------------------------------------------------------- #
# One PDF
# --------------------------------------------------------------------------- #


def check_pdf(abs_path: Path, *, run_ocr: bool = True) -> str:
    """Record the PDF's state and OCR it in place when it has no text layer.

    Returns one of ``gone``, ``unchanged``, ``has_text``, ``pending``,
    ``ocr_done``, ``ocr_failed``, ``unreadable``.
    """
    rel_path = rel(abs_path)
    try:
        st = abs_path.stat()
    except FileNotFoundError:
        PdfFile.objects.filter(path=rel_path).delete()
        return "gone"

    row, created = PdfFile.objects.get_or_create(
        path=rel_path, defaults={"size": st.st_size, "mtime": st.st_mtime}
    )
    same_version = row.size == st.st_size and row.mtime == st.st_mtime
    # A failed OCR is tried again on later passes until the attempts run
    # out; after that the file is settled until it changes.
    settled = row.ocr_status in ("none", "done") or (
        row.ocr_status == "failed" and row.attempts >= MAX_ATTEMPTS
    )
    if not created and same_version and row.checked_at and settled:
        return "unchanged"
    if not same_version:
        row.attempts = 0

    row.size, row.mtime = st.st_size, st.st_mtime
    row.has_text = ocr.has_text(abs_path)
    row.checked_at = timezone.now()

    if row.has_text is None:
        row.ocr_status = "failed"
        row.ocr_error = (
            "The file is empty (0 bytes)."
            if st.st_size == 0
            else "The PDF could not be read."
        )
        row.attempts = MAX_ATTEMPTS
        row.save()
        return "unreadable"
    if row.has_text:
        row.ocr_status, row.ocr_error = "none", ""
        row.save()
        text.warm(abs_path)
        return "has_text"
    if not run_ocr:
        row.ocr_status = "pending"
        row.save()
        return "pending"
    if row.attempts >= MAX_ATTEMPTS:
        row.ocr_status = "failed"
        row.save()
        return "ocr_failed"

    row.ocr_status = "pending"
    row.attempts += 1
    row.save()
    logger.info("OCR %s", rel_path)
    try:
        ocr.ocr_in_place(abs_path)
    except ocr.OcrError as exc:
        row.ocr_status, row.ocr_error = "failed", str(exc)[:2000]
        if exc.permanent:
            row.attempts = MAX_ATTEMPTS
        row.save()
        logger.warning("OCR failed for %s: %s", rel_path, exc)
        return "ocr_failed"

    st = abs_path.stat()
    row.size, row.mtime = st.st_size, st.st_mtime
    row.has_text = True
    row.ocr_status, row.ocr_error = "done", ""
    row.ocr_at = timezone.now()
    row.save()
    text.warm(abs_path)
    return "ocr_done"


# --------------------------------------------------------------------------- #
# Links and the free-folder list
# --------------------------------------------------------------------------- #


def refresh_links() -> FilesState:
    """Flag linked folders that are missing and recompute the unclaimed list."""
    now = timezone.now()
    for folder in MatterFolder.objects.all():
        if folder.exists:
            if folder.missing_since is not None:
                folder.missing_since = None
                folder.save(update_fields=["missing_since"])
        elif folder.missing_since is None:
            folder.missing_since = now
            folder.save(update_fields=["missing_since"])
    state = FilesState.get()
    state.unclaimed_folders = tree.unclaimed_folders()
    state.save(update_fields=["unclaimed_folders"])
    return state


def follow_rename(old_rel: str, new_rel: str) -> int:
    """A directory moved: every link at or under the old path moves with it."""
    moved = 0
    for folder in MatterFolder.objects.filter(
        Q(path=old_rel) | Q(path__startswith=old_rel + "/")
    ):
        folder.path = new_rel + folder.path[len(old_rel) :]
        folder.missing_since = None
        folder.save(update_fields=["path", "missing_since"])
        moved += 1
    if moved:
        logger.info("Followed rename %s -> %s (%d link(s))", old_rel, new_rel, moved)
    return moved


# --------------------------------------------------------------------------- #
# Full scan
# --------------------------------------------------------------------------- #


def scan(*, run_ocr: bool = True, progress=None) -> dict:
    """Walk the whole tree once. Returns the outcome counts."""
    base = tree.root()
    if base is None or not base.is_dir():
        raise RuntimeError("DROPBOX_FIRM_ROOT is not set or is not a directory.")
    stats: Counter = Counter()
    seen = set()
    empty = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if not tree.is_ignored(d))
        for filename in filenames:
            if tree.is_hidden(filename):
                continue
            abs_path = Path(dirpath) / filename
            rel_path = rel(abs_path)
            try:
                if abs_path.stat().st_size == 0:
                    empty.append(rel_path)
            except OSError:
                continue
            if not filename.lower().endswith(PDF_SUFFIX) or tree.ocr_excluded(rel_path):
                continue
            seen.add(rel_path)
            result = check_pdf(abs_path, run_ocr=run_ocr)
            stats[result] += 1
            if progress and result not in ("unchanged", "has_text"):
                progress(f"{result}: {rel_path}")
    stats["empty_files"] = len(empty)
    # Rows for files that are no longer in the tree.
    stale = PdfFile.objects.exclude(path__in=seen)
    stats["removed"] = stale.count()
    stale.delete()

    state = refresh_links()
    previous = set(state.empty_files)
    state.new_empty_files = (
        [path for path in empty if path not in previous] if state.scanned_at else []
    )
    state.empty_files = empty[:EMPTY_FILES_KEPT]
    state.scanned_at = timezone.now()
    state.scan_stats = dict(stats)
    state.save(
        update_fields=["scanned_at", "scan_stats", "empty_files", "new_empty_files"]
    )
    return dict(stats)


# --------------------------------------------------------------------------- #
# The inotify loop
# --------------------------------------------------------------------------- #


class Watcher:
    """The long-running loop. ``run()`` blocks until ``stop()`` or Ctrl-C."""

    def __init__(self, *, run_ocr: bool = True, scan_on_start: bool = True):
        self.run_ocr = run_ocr
        self.scan_on_start = scan_on_start
        self._pending: dict[str, float] = {}
        self._moves: dict[int, tuple[float, str]] = {}
        self._links_dirty_at: float | None = None
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._last_heartbeat = 0.0
        self._last_scan = 0.0

    def stop(self):
        self._stop.set()

    # -- event handling ---------------------------------------------------

    def handle(self, types, rel_path: str, cookie: int, now: float) -> None:
        """Reduce one inotify event to pending work. Pure bookkeeping,
        so it is testable without a filesystem."""
        if tree.is_ignored(rel_path):
            return
        is_dir = "IN_ISDIR" in types
        if is_dir:
            if "IN_MOVED_FROM" in types:
                self._moves[cookie] = (now, rel_path)
            elif "IN_MOVED_TO" in types:
                old = self._moves.pop(cookie, None)
                if old is not None:
                    follow_rename(old[1], rel_path)
                self._links_dirty_at = now
            elif "IN_CREATE" in types or "IN_DELETE" in types:
                self._links_dirty_at = now
            return
        if not rel_path.lower().endswith(PDF_SUFFIX) or tree.ocr_excluded(rel_path):
            return
        if "IN_CLOSE_WRITE" in types or "IN_MOVED_TO" in types:
            self._pending[rel_path] = now
        elif "IN_DELETE" in types or "IN_MOVED_FROM" in types:
            self._pending.pop(rel_path, None)
            PdfFile.objects.filter(path=rel_path).delete()

    def flush(self, now: float) -> list[str]:
        """Hand debounced PDFs to the worker and refresh links when due.
        Returns the paths queued (for tests)."""
        due = [p for p, t in self._pending.items() if now - t >= DEBOUNCE_SECONDS]
        for path in due:
            del self._pending[path]
            self._queue.put(path)
        # A rename whose other half never came is a delete.
        for cookie, (t, _) in list(self._moves.items()):
            if now - t > MOVE_COOKIE_TTL:
                del self._moves[cookie]
                self._links_dirty_at = now
        if (
            self._links_dirty_at is not None
            and now - self._links_dirty_at >= DEBOUNCE_SECONDS
        ):
            self._links_dirty_at = None
            refresh_links()
        return due

    # -- the loop -----------------------------------------------------------

    def _worker(self):
        base = tree.root()
        while not self._stop.is_set():
            try:
                rel_path = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            try:
                close_old_connections()
                result = check_pdf(base / rel_path, run_ocr=self.run_ocr)
                if result not in ("unchanged", "has_text"):
                    logger.info("%s: %s", result, rel_path)
            except Exception:
                logger.exception("Checking %s failed", rel_path)
            finally:
                self._queue.task_done()

    def _heartbeat(self, now: float):
        if now - self._last_heartbeat < HEARTBEAT_SECONDS:
            return
        self._last_heartbeat = now
        close_old_connections()
        FilesState.objects.filter(pk=FilesState.get().pk).update(
            watcher_seen_at=timezone.now()
        )

    def _maybe_scan(self, now: float):
        if now - self._last_scan < SCAN_INTERVAL_SECONDS:
            return
        self._last_scan = now
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        try:
            close_old_connections()
            stats = scan(run_ocr=self.run_ocr)
            logger.info("Scan: %s", stats)
        except Exception:
            logger.exception("Scan failed")

    def run(self):
        # The inotify package reads DEBUG from the environment as an int at
        # import; the project's .env sets it to "True" for Django.
        if not os.environ.get("DEBUG", "0").isdigit():
            os.environ["DEBUG"] = "0"
        import inotify.adapters
        import inotify.constants as C

        base = tree.root()
        if base is None or not base.is_dir():
            raise RuntimeError("DROPBOX_FIRM_ROOT is not set or is not a directory.")
        mask = (
            C.IN_CLOSE_WRITE
            | C.IN_MOVED_FROM
            | C.IN_MOVED_TO
            | C.IN_CREATE
            | C.IN_DELETE
        )
        logger.info("Watching %s", base)
        watch = inotify.adapters.InotifyTree(str(base), mask=mask)
        worker = threading.Thread(target=self._worker, daemon=True)
        worker.start()
        self._last_scan = time.monotonic() if not self.scan_on_start else 0.0
        try:
            # No timeout_s: in this library it is an idle timeout that ends the
            # generator. With yield_nones the loop wakes about once a second
            # regardless, which drives flush, heartbeat and the daily scan.
            for event in watch.event_gen(yield_nones=True):
                if self._stop.is_set():
                    break
                now = time.monotonic()
                if event is not None:
                    header, types, watch_path, filename = event
                    abs_path = (
                        Path(watch_path) / filename if filename else Path(watch_path)
                    )
                    try:
                        rel_path = rel(abs_path)
                    except ValueError:
                        continue
                    self.handle(types, rel_path, header.cookie, now)
                self.flush(now)
                self._heartbeat(now)
                self._maybe_scan(now)
        except KeyboardInterrupt:
            pass
        finally:
            self._stop.set()
            worker.join(timeout=5)
