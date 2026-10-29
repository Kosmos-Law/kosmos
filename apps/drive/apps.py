"""Firm files: the Dropbox tree synced onto this host.

The firm keeps its files in Dropbox. The Dropbox daemon syncs the Firm
folder onto the server, and this app works with the files where they are:
it links a matter to its folder (a person chooses; the app only suggests),
watches the tree so links follow renames and every PDF carries a text
layer (OCR in place), and reports the tree's state under Settings. Nothing
is copied into the database; the AI agent reads the files from disk.
Record: docs/decisions/2026-10-29-firm-files-live-in-dropbox.md.
"""

from django.apps import AppConfig


class DriveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.drive"
    verbose_name = "Firm files"
