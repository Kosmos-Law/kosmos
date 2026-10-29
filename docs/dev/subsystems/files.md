# Files

`apps/drive`. The firm's files live in Dropbox; the Dropbox daemon syncs
the Firm folder onto the server and this app works with the tree where
it is. Record: [Firm files live in Dropbox, and the AI reads them in
place (2026-10-29)](../../decisions/2026-10-29-firm-files-live-in-dropbox.md).

## Configuration

| Setting | Meaning |
| --- | --- |
| `DROPBOX_FIRM_ROOT` | The synced Firm folder on this host. Empty turns the integration off: no Files row, no watcher. |
| `DROPBOX_MATTER_ROOTS` | Subfolders of the root whose direct children are matter folders. Default `Matters - Open`, `Matters - Pending`. |
| `DROPBOX_OCR_EXCLUDE` | Top-level folders the watcher never checks or OCRs. Default `Matters - Closed`: an archive the firm does not work in, and the one place the first scan found PDFs without text in bulk. |
| `FILES_OCR_SCRATCH` | Where OCR output is staged before the atomic replace. Keep it on the tree's filesystem. Default `<app>/.ocr-scratch`. |
| `FILES_OCR_JOBS` | Tesseract workers per file. Default 2. |

The Dropbox daemon runs under the same account as the watcher
(`~/.dropbox-dist/dropboxd`, with the `dropbox` CLI for status and
selective sync). `fs.inotify.max_user_watches` needs raising; the tree
has over ten thousand directories.

## Modules

- `tree.py`: path arithmetic over the root. Which folders are matters
  (`list_matter_folders`), which are free (`unclaimed_folders`), what the
  picker suggests (`suggest`, a normalised name match at or above 0.6),
  what is ignored (`.dropbox*`, dotfiles, LibreOffice lock files).
- `ocr.py`: `has_text` samples the first pages with pypdf;
  `ocr_in_place` runs OCRmyPDF (`skip_text`, plain PDF output, no
  deskew) into the scratch directory and `os.replace`s the original.
- `watcher.py`: `check_pdf` records one PDF's state in `PdfFile` and
  OCRs it when the text layer is missing (three attempts per version of
  the file, then left as failed); `refresh_links` flags missing linked
  folders and recomputes the unclaimed list; `follow_rename` moves links
  under a renamed directory; `scan` walks the tree once; `Watcher` is the
  inotify loop, with `handle`/`flush` as a pure reducer (debounce,
  move-cookie pairing) and one worker thread for OCR so a long job never
  blocks the event queue.
- `views.py`: the Link Folder modal and its link/unlink posts (matter
  access required; another matter's folder is shown taken, named only if
  the user is on that matter), and Settings > Files for admins.
- `templatetags/drive_tags.py`: `matter_folder_chip` (the AI tab's
  toolbar chip) and `files_integration_card` (Settings > Integrations). The core
  loads these by name, which keeps the import-linter boundary intact.

## Running it

- `manage.py watch_files`: the service (`deploy/systemd/files-watcher.service`).
  A full scan first, then inotify; heartbeat every 30 s to
  `FilesState.watcher_seen_at`, which the status page turns into
  "Running" or "Not reporting".
- `manage.py watch_files --scan`: one full pass and exit.
- `manage.py watch_files --scan --no-ocr`: record which PDFs lack a text
  layer without touching any.

## Empty files

Every scan also lists zero-byte files of any type anywhere in the tree,
closed matters included, and the status page shows the count, the ones
that were not there the scan before, and the full list. A file that
arrives empty is a failed copy or extraction (a ZIP unpacked into a
streaming Drive folder, a WhatsApp export of media the phone never
downloaded), and the point is that someone sees it the next day rather
than months later.

## What it never does

Infer a matter's folder; remove a link on its own; write anything into
the tree other than a text layer on a PDF that has none; copy files into
the database.
