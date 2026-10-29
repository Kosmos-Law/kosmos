"""The synced Firm tree: where it is, which folders are matters, which are free.

Everything here is path arithmetic over ``settings.DROPBOX_FIRM_ROOT``.
Matter folders are the direct children of the configured matter roots
("Matters - Open", "Matters - Pending"); the closed-matter tree is bucketed
by year and gets no per-matter links.
"""

import difflib
import re
from pathlib import Path

from django.conf import settings

# Folders under a matter root that are not matters.
ARCHIVE_NAMES = {"0 Archive"}
# Directories the watcher and the scan never look inside.
IGNORED_DIRS = {".dropbox", ".dropbox.cache"}

SUGGESTION_THRESHOLD = 0.6


def root() -> Path | None:
    value = settings.DROPBOX_FIRM_ROOT
    return Path(value) if value else None


def configured() -> bool:
    """The Files integration is on when the synced tree is on disk."""
    path = root()
    return path is not None and path.is_dir()


def matter_roots() -> list[str]:
    return list(settings.DROPBOX_MATTER_ROOTS)


def is_hidden(name: str) -> bool:
    return name.startswith(".")


def is_ignored(rel_path: str) -> bool:
    """Dropbox's own directories, dotfiles and LibreOffice lock files."""
    parts = rel_path.split("/")
    return any(part in IGNORED_DIRS or is_hidden(part) for part in parts)


def ocr_excluded(rel_path: str) -> bool:
    """Under a top-level folder the watcher leaves alone (closed matters)."""
    return rel_path.split("/", 1)[0] in settings.DROPBOX_OCR_EXCLUDE


def is_matter_folder_name(name: str) -> bool:
    return not is_hidden(name) and name not in ARCHIVE_NAMES


def list_matter_folders() -> list[str]:
    """Every folder that could be a matter, as ``<root>/<name>`` paths."""
    base = root()
    if base is None:
        return []
    found = []
    for root_name in matter_roots():
        directory = base / root_name
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_dir() and is_matter_folder_name(entry.name):
                found.append(f"{root_name}/{entry.name}")
    return found


def folder_name(path: str) -> str:
    return path.rsplit("/", 1)[-1]


_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def normalize(name: str) -> str:
    return _NORMALIZE_RE.sub(" ", (name or "").lower()).strip()


def score(matter_name: str, path: str) -> float:
    """How well a folder name matches a matter name: 1.0 is exact."""
    a, b = normalize(matter_name), normalize(folder_name(path))
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def suggest(matter_name: str, paths: list[str]) -> str | None:
    """The one folder worth proposing for this matter, or None.

    A suggestion is only ever shown; nothing links until a person clicks.
    """
    best, best_score = None, 0.0
    for path in paths:
        value = score(matter_name, path)
        if value > best_score:
            best, best_score = path, value
    return best if best_score >= SUGGESTION_THRESHOLD else None


def unclaimed_folders() -> list[str]:
    """Matter-root folders no matter is linked to."""
    from .models import MatterFolder

    linked = set(MatterFolder.objects.values_list("path", flat=True))
    return [path for path in list_matter_folders() if path not in linked]
