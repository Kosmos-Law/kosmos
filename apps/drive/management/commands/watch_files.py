"""Watch the synced Firm tree (the ``files-watcher`` service), or scan it once.

manage.py watch_files            # run the watcher until stopped
manage.py watch_files --scan     # one full pass, then exit
manage.py watch_files --scan --no-ocr   # report PDFs lacking text, OCR nothing
"""

import logging

from django.core.management.base import BaseCommand, CommandError

from apps.drive import tree, watcher


class Command(BaseCommand):
    help = "Watch the synced Firm tree: OCR new PDFs in place, follow folder renames."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scan", action="store_true", help="Walk the whole tree once and exit."
        )
        parser.add_argument(
            "--no-ocr",
            action="store_true",
            help="Only record which PDFs lack a text layer; never run OCR.",
        )
        parser.add_argument(
            "--no-initial-scan",
            action="store_true",
            help="Start watching without the full pass the watcher runs first.",
        )

    def handle(self, *args, **options):
        if not tree.configured():
            raise CommandError(
                "DROPBOX_FIRM_ROOT is not set or is not a directory "
                f"({tree.root() or 'unset'})."
            )
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        run_ocr = not options["no_ocr"]
        if options["scan"]:
            stats = watcher.scan(run_ocr=run_ocr, progress=self.stdout.write)
            self.stdout.write(
                ", ".join(f"{key} {value}" for key, value in sorted(stats.items()))
                or "nothing found"
            )
            return
        watcher.Watcher(
            run_ocr=run_ocr, scan_on_start=not options["no_initial_scan"]
        ).run()
