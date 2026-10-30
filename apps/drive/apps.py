"""Migrations only: the shell that drops the removed Google Drive mirror's
tables and, after it, the removed Files integration's (matter-to-folder
links and the watcher's state). The firm's files live in Dropbox and are
indexed by firm-index on the office server; Claude reads them there.
Records: docs/decisions/2026-10-27-google-drive-removed.md,
docs/decisions/2026-10-30-ai-chat-retired.md.
"""

from django.apps import AppConfig


class DriveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.drive"
    verbose_name = "Firm files (retired)"
