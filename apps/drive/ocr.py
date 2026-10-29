"""Every PDF in the tree carries a text layer, added in place.

The agent reads PDFs straight off the disk, so a scanned PDF with no text
layer is invisible to it. The watcher checks each new or changed PDF and,
when the text layer is missing, runs OCRmyPDF over it and replaces the
file. Safeguards:

- ``skip_text``: pages that already have text are never re-rendered, and
  the watcher's own output never triggers a second pass.
- plain ``pdf`` output, no deskew, no optimisation: the file looks as it
  did; only the invisible text layer is added.
- the OCR'd file is written outside the tree and moved into place in one
  rename, so Dropbox never syncs a half-written PDF.

Dropbox keeps the previous version of every file, so an OCR pass that
somehow goes wrong is recoverable from its version history.
"""

import errno
import logging
import os
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# Pages sampled when deciding whether a PDF has a text layer, and the
# characters those pages must hold between them. A scanned PDF yields
# nothing; a born-digital cover page alone clears this easily.
SAMPLE_PAGES = 3
MIN_CHARS = 40


class OcrError(Exception):
    """OCR did not produce a replacement file; the original is untouched."""


def text_chars(path: Path, pages: int = SAMPLE_PAGES) -> int | None:
    """Characters of text on the first ``pages`` pages, or None if the PDF
    cannot be read (damaged, or encrypted with a password)."""
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return None
        total = 0
        for index, page in enumerate(reader.pages):
            if index >= pages:
                break
            try:
                total += len((page.extract_text() or "").strip())
            except Exception:
                # Malformed fonts on one page: count what the others give.
                continue
        return total
    except Exception as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None


def has_text(path: Path) -> bool | None:
    chars = text_chars(path)
    if chars is None:
        return None
    return chars >= MIN_CHARS


def ocr_in_place(path: Path, jobs: int | None = None) -> None:
    """Add a text layer to ``path``; raises OcrError and leaves it alone on
    failure."""
    import ocrmypdf

    scratch = Path(settings.FILES_OCR_SCRATCH)
    scratch.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".pdf", dir=scratch)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        try:
            ocrmypdf.ocr(
                str(path),
                str(tmp),
                language=["eng"],
                skip_text=True,
                output_type="pdf",
                optimize=0,
                jobs=jobs or settings.FILES_OCR_JOBS,
                progress_bar=False,
            )
        except Exception as exc:
            raise OcrError(f"{type(exc).__name__}: {exc}") from exc
        if tmp.stat().st_size == 0:
            raise OcrError("OCR produced an empty file")
        shutil.copymode(path, tmp)
        _replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _replace(tmp: Path, path: Path) -> None:
    """Move the finished file over the original atomically.

    ``os.replace`` is atomic on one filesystem. When the scratch directory
    sits on another, the file is first copied to a dotfile beside the
    original (Dropbox ignores it for the moment it exists) and renamed
    from there.
    """
    try:
        os.replace(tmp, path)
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise
        staged = path.with_name(f".{path.name}.kosmos-ocr")
        shutil.copyfile(tmp, staged)
        shutil.copymode(path, staged)
        os.replace(staged, path)
