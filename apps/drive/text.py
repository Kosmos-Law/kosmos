"""The text inside the tree's documents, for searching across a folder.

ripgrep, the harness's Grep, reads bytes: a PDF's text layer and the
XML inside an ODT or DOCX are invisible to it, so "find every mention of
the lender in Record" finds nothing. ``search`` walks a folder, takes
each document's text (PDF through pdftotext, ODT and DOCX from their
XML, plain text as it is) and matches a pattern against it, reporting
the file, the page for a PDF, and the matching line.

Extracted text is cached outside the sync tree (``FILES_TEXT_CACHE``),
one file per document keyed by its path and validated by size and
mtime, so a folder is slow to search once and quick after; the watcher
warms the cache for each PDF it checks.
"""

import hashlib
import logging
import os
import re
import subprocess
import time
import zipfile
from html import unescape
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

DOCUMENT_TYPES = {".pdf", ".odt", ".docx"}
TEXT_TYPES = {".txt", ".md", ".csv", ".eml"}
SUPPORTED = DOCUMENT_TYPES | TEXT_TYPES
PAGE_BREAK = "\f"
MAX_CHARS = 4_000_000
PDFTOTEXT_TIMEOUT = 120

_XML_BREAKS = re.compile(r"</text:p>|</text:h>|</w:p>|<text:line-break/>|<w:br/>")
_XML_TABS = re.compile(r"<text:tab/>|<w:tab/>")
_XML_SPACES = re.compile(r"<text:s(?: text:c=\"(\d+)\")?/>")
_XML_TAGS = re.compile(r"<[^>]+>")
_BLANK_LINES = re.compile(r"\n{3,}")


class TextError(Exception):
    """The file's text could not be taken."""


def cache_dir() -> Path:
    return Path(settings.FILES_TEXT_CACHE)


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #


def extract(path: Path) -> str:
    """The text of one file, pages separated by form feeds for a PDF."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_text(path)
    if suffix in (".odt", ".docx"):
        return _office_text(
            path, "content.xml" if suffix == ".odt" else "word/document.xml"
        )
    if suffix in TEXT_TYPES:
        try:
            return path.read_text(errors="replace")[:MAX_CHARS]
        except OSError as exc:
            raise TextError(str(exc)) from exc
    return ""


def _pdf_text(path: Path) -> str:
    try:
        done = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            timeout=PDFTOTEXT_TIMEOUT,
            check=False,
        )
    except FileNotFoundError as exc:
        raise TextError("pdftotext is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise TextError("pdftotext timed out") from exc
    if done.returncode != 0:
        raise TextError(
            done.stderr.decode(errors="replace").strip().splitlines()[-1:][0]
            if done.stderr.strip()
            else f"pdftotext exited {done.returncode}"
        )
    return done.stdout.decode("utf-8", errors="replace")[:MAX_CHARS]


def _office_text(path: Path, member: str) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read(member).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise TextError(f"not a readable document: {exc}") from exc
    xml = _XML_BREAKS.sub("\n", xml)
    xml = _XML_TABS.sub("\t", xml)
    xml = _XML_SPACES.sub(lambda m: " " * int(m.group(1) or 1), xml)
    text = unescape(_XML_TAGS.sub("", xml))
    return _BLANK_LINES.sub("\n\n", text).strip()[:MAX_CHARS]


# --------------------------------------------------------------------------- #
# The cache
# --------------------------------------------------------------------------- #


def _cache_file(path: Path) -> Path:
    key = hashlib.sha1(str(path).encode()).hexdigest()
    return cache_dir() / key[:2] / f"{key}.txt"


def text_of(path: Path) -> str:
    """The file's text, from the cache when it is current."""
    st = path.stat()
    stamp = f"{st.st_size} {st.st_mtime_ns}\n"
    cached = _cache_file(path)
    try:
        with cached.open(encoding="utf-8") as fh:
            if fh.readline() == stamp:
                return fh.read()
    except OSError:
        pass
    text = extract(path)
    try:
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(stamp + text, encoding="utf-8")
        tmp.replace(cached)
    except OSError as exc:
        logger.warning("Text cache write failed for %s: %s", path, exc)
    return text


def warm(path: Path) -> bool:
    """Fill the cache for one file; False when its text could not be taken."""
    if path.suffix.lower() not in SUPPORTED:
        return False
    try:
        text_of(path)
        return True
    except (TextError, OSError) as exc:
        logger.info("No text for %s: %s", path, exc)
        return False


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #


def _files(root: Path) -> list[Path]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if not name.startswith(".") and Path(name).suffix.lower() in SUPPORTED:
                found.append(Path(dirpath) / name)
    return found


def _snippet(text: str, start: int, end: int, width: int = 220) -> tuple[int, str]:
    """The line holding a match, whitespace collapsed and windowed around
    the match when it is long. Returns (line start, snippet)."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end]
    if len(line) > width:
        lead = max(0, start - line_start - width // 3)
        line = ("..." if lead else "") + line[lead : lead + width] + "..."
    return line_start, " ".join(line.split())


def search(
    folder: Path,
    pattern: str,
    *,
    subpath: str = "",
    regex: bool = False,
    limit: int = 60,
    per_file: int = 6,
    budget: float = 20.0,
) -> dict:
    """Matches of ``pattern`` (case-insensitive; literal unless ``regex``)
    in the documents under ``folder`` or its ``subpath``."""
    folder = folder.resolve()
    root = (folder / subpath).resolve() if subpath else folder
    if root != folder and folder not in root.parents:
        return {"error": "path must be inside the matter folder"}
    if not root.is_dir():
        return {"error": f"no folder named {subpath!r} in the matter folder"}
    try:
        needle = re.compile(pattern if regex else re.escape(pattern), re.IGNORECASE)
    except re.error as exc:
        return {"error": f"bad pattern: {exc}"}

    files = _files(root)
    hits, failed = [], []
    files_with_hits = searched = 0
    started = time.monotonic()
    stopped = False
    for path in files:
        if len(hits) >= limit or time.monotonic() - started > budget:
            stopped = True
            break
        searched += 1
        rel = path.relative_to(folder).as_posix()
        try:
            text = text_of(path)
        except (TextError, OSError):
            failed.append(rel)
            continue
        is_pdf = path.suffix.lower() == ".pdf"
        count, last_line = 0, -1
        for match in needle.finditer(text):
            line_start, snippet = _snippet(text, match.start(), match.end())
            if line_start == last_line:
                continue
            last_line = line_start
            count += 1
            if count <= per_file:
                hits.append(
                    {
                        "file": rel,
                        "page": text.count(PAGE_BREAK, 0, match.start()) + 1
                        if is_pdf
                        else None,
                        "text": snippet,
                    }
                )
        if count:
            files_with_hits += 1
            if count > per_file:
                hits.append(
                    {
                        "file": rel,
                        "page": None,
                        "text": f"... and {count - per_file} more",
                    }
                )
    return {
        "pattern": pattern,
        "where": root.relative_to(folder).as_posix() if root != folder else "",
        "hits": hits,
        "files_searched": searched,
        "files_total": len(files),
        "files_with_hits": files_with_hits,
        "failed": failed,
        "stopped": stopped,
    }


def format_search(result: dict) -> str:
    """The search result as the model reads it."""
    if "error" in result:
        return result["error"]
    where = f" under {result['where']}" if result["where"] else ""
    pattern = result["pattern"]
    total = result["files_total"]
    if not result["hits"]:
        lines = [f"No hits for {pattern!r} in {total} files{where}."]
    else:
        shown = sum(1 for h in result["hits"] if not h["text"].startswith("... and "))
        lines = [
            f"{shown} hits in {result['files_with_hits']} of "
            f"{result['files_searched']} files for {pattern!r}{where}:"
        ]
        current = None
        for hit in result["hits"]:
            if hit["file"] != current:
                current = hit["file"]
                lines.append(f"\n{current}")
            page = f"p.{hit['page']}: " if hit["page"] else ""
            lines.append(f"  {page}{hit['text']}")
    if result["stopped"]:
        lines.append(
            f"\nStopped after {result['files_searched']} of {total} files "
            "(enough hits, or out of time): narrow the search with path or a "
            "more specific pattern."
        )
    if result["failed"]:
        lines.append("\nCould not read: " + ", ".join(result["failed"][:10]))
    return "\n".join(lines)
