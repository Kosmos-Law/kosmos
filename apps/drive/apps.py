"""The retired Google Drive mirror.

The firm moved its files to Dropbox and the Drive integration was removed
(docs/decisions/2026-10-27-google-drive-removed.md). Only the migrations
are left, so the one that drops the Drive tables runs everywhere; a later
release deletes the package and takes it out of INSTALLED_APPS.
"""

from django.apps import AppConfig


class DriveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.drive"
