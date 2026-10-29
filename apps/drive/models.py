"""The firm's files live in Dropbox; these rows only say where.

``MatterFolder`` is the one link a person makes: this matter's folder in
the synced tree. ``PdfFile`` remembers what the watcher found out about
each PDF (text layer present, OCR done or failed) so a nightly scan does
not re-open 10,000 files and a PDF that cannot be OCR'd is not retried
forever. ``FilesState`` is the single row the Settings page reads.
"""

from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


class MatterFolder(models.Model):
    """A matter's folder in the Firm tree, chosen by a person.

    ``path`` is relative to ``settings.DROPBOX_FIRM_ROOT`` and uses ``/``,
    e.g. ``Matters - Open/Smith v Jones``. The filesystem has no stable
    folder id, so the watcher follows renames to keep the path current and
    flags a folder it can no longer find rather than unlinking it.
    """

    matter = models.OneToOneField(
        "matters.Matter", on_delete=models.CASCADE, related_name="folder"
    )
    path = models.CharField(max_length=1024, unique=True)
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    linked_at = models.DateTimeField(default=timezone.now)
    missing_since = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_drive_matter_folder"

    def __str__(self):
        return self.path

    @property
    def name(self):
        return self.path.rsplit("/", 1)[-1]

    @property
    def root_name(self):
        """The matter root the folder sits in ("Matters - Open")."""
        return self.path.split("/", 1)[0]

    def absolute_path(self) -> Path | None:
        root = settings.DROPBOX_FIRM_ROOT
        if root is None:
            return None
        return Path(root) / self.path

    @property
    def exists(self) -> bool:
        absolute = self.absolute_path()
        return absolute is not None and absolute.is_dir()


class PdfFile(models.Model):
    """What the watcher knows about one PDF in the tree.

    Keyed by path; ``size`` and ``mtime`` say which version of the file the
    row describes, so an unchanged file is skipped on the next scan and an
    edited one is checked again from scratch.
    """

    OCR_STATUS_CHOICES = [
        ("none", "Not needed"),
        ("pending", "Pending"),
        ("done", "Done"),
        ("failed", "Failed"),
    ]

    path = models.CharField(max_length=1024, unique=True)
    size = models.BigIntegerField(default=0)
    mtime = models.FloatField(default=0.0)
    has_text = models.BooleanField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    ocr_status = models.CharField(
        max_length=10, choices=OCR_STATUS_CHOICES, default="none"
    )
    ocr_error = models.TextField(blank=True, default="")
    ocr_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "app_drive_pdf_file"

    def __str__(self):
        return self.path

    @property
    def name(self):
        return self.path.rsplit("/", 1)[-1]


class FilesState(models.Model):
    """One row: the tree as the watcher last saw it."""

    unclaimed_folders = models.JSONField(default=list, blank=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    scan_stats = models.JSONField(default=dict, blank=True)
    watcher_seen_at = models.DateTimeField(null=True, blank=True)
    # Zero-byte files of any type, anywhere in the tree, as the last scan
    # found them, and the ones that were not there the scan before. A file
    # that arrives empty is a sign of a failed copy or extraction, and the
    # status page is where someone sees it.
    empty_files = models.JSONField(default=list, blank=True)
    new_empty_files = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "app_drive_files_state"

    @classmethod
    def get(cls):
        state, _ = cls.objects.get_or_create(pk=1)
        return state

    def __str__(self):
        return "Files state"
