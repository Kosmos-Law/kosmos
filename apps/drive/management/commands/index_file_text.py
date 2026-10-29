"""Warm the document text cache for the matter folders.

The sessions' search inside files extracts text on first use and caches
it; this fills the cache ahead of time for the files already in the tree
(the watcher keeps it warm for new and changed PDFs).
"""

import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.drive import text, tree


class Command(BaseCommand):
    help = "Extract and cache the text of PDFs and documents under the matter roots."

    def add_arguments(self, parser):
        parser.add_argument(
            "folders",
            nargs="*",
            help="Top-level folders to index (default: DROPBOX_MATTER_ROOTS).",
        )

    def handle(self, *args, **options):
        root = tree.root()
        folders = options["folders"] or settings.DROPBOX_MATTER_ROOTS
        started = time.monotonic()
        done = failed = 0
        for name in folders:
            for path in text._files(root / name):
                if text.warm(path):
                    done += 1
                else:
                    failed += 1
                if (done + failed) % 500 == 0:
                    self.stdout.write(
                        f"{done + failed} files, {int(time.monotonic() - started)}s"
                    )
        self.stdout.write(
            f"Indexed {done} files ({failed} without text) in {int(time.monotonic() - started)}s."
        )
