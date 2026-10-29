# Google Drive is removed (2026-10-27)

Since June 2026 Kosmos read the firm's files from Google Drive. A
matter's Drive folder was linked from the Documents tab, its top-level
subfolders were mapped to a category and a proceeding, and a mirror on
the worker (the Drive Changes API every minute, a full crawl each night)
copied the PDFs under the mapped folders into the matter's documents:
append-only, PDF-only and read-only on Drive, with a tombstone so a
document deleted in Kosmos did not come back. Drafting leaned on the
same connection: a draft was linked by picking an `.odt` from the
matter's Drive folder, and the server re-read a stale draft from Drive
when no companion was connected.

The firm has moved its files to Dropbox. Nothing is left in Drive for the
mirror to read.

## Decision

The Google Drive integration and the document mirror are removed, not
kept dormant. A mirror over a folder tree the firm no longer uses would
only be code to maintain and a connection to explain; the Dropbox
integration will be built against the files where they now are.

The documents the mirror brought in are kept. They are ordinary
documents in every respect: they can be moved to another matter and
their file replaced like any upload.

Linking a new draft is turned off until there is a Dropbox-based way to
pick the file. Existing draft links keep working through the LibreOffice
companion as before: the companion pushes the live document, AI edits
apply as tracked changes, and a draft can be unlinked.
`DraftLink.drive_file_id` stays as the file's identity for those links
(the companion API's `file` field).

## What was removed

- The mirror in `apps/drive`: the Changes API sync (`google.py`), the
  upsert (`records.py`), the folder mappings (`mappings.py`), the
  tombstone signal, and the models `DriveFolderMapping`,
  `DriveMatterState`, `DriveRecordTombstone` and the sync-state row.
- The scheduled jobs `drive-sync` and `drive-sync-nightly-full`, and the
  management commands `link_drive_folders`, `restore_drive_documents`
  and `sync_drive_notes`.
- On the Documents tab, the **Link Drive Folder** / **Drive Folder**
  button and its modal (link a matter's folder, map subfolders, unlink),
  and the rules that kept a Drive document on its folder's matter and
  its file unreplaced.
- Under Settings > Integrations, the Google Drive row; under Settings >
  Features, the line saying the case-file switch pauses the mirror.
  Google Calendar, Google Contacts and Gmail are unchanged.
- The `drive.readonly` OAuth scope, and the settings
  `GOOGLE_DRIVE_TOKEN_PATH`, `DRIVE_NOTES_ROOT` and
  `DRIVE_SHARED_DRIVE_ID`.
- The `matter_closed` signal (`apps/matters/signals.py`), whose only
  listener was the mirror. Closing a matter still clears its Gmail label
  and starts the chat clock.
- In drafts: the picker and link routes, `apps/drafts/services.py`, the
  re-fetch of a stale draft from Drive, the draft button in the chat
  composer for a conversation with no draft, and the
  `ai:create-conversation` route that existed so a draft could be linked
  in a fresh chat window.

## What moved

- The file converter (`.docx` and `.odt` through pandoc; `.xlsx`, `.ods`
  and `.csv` to Markdown tables), used by mail attachments and drafts:
  `apps/drive/convert.py` to `utils/convert.py`.
- The headless LibreOffice redline driver, still dormant and tested:
  `apps/drive/redline.py` and `uno_driver.py` to
  `apps/drafts/redline.py` and `apps/drafts/uno_driver.py`. pandoc,
  `soffice` and `UNO_PYTHON` stay in the system requirements.

## What the migrations drop

- `apps/case/migrations/0097_remove_document_drive_fields.py`: on
  `Document`, `drive_file_id`, `drive_path`, `drive_modified`,
  `drive_synced_at` and `drive_mapping`.
- `apps/matters/migrations/0057_remove_matter_drive_folder.py`:
  `Matter.drive_folder` and `Matter.drive_folder_id`.
- `apps/drive/migrations/0005_drive_removed.py`: every `apps.drive`
  table, and the `drive-sync` and `drive-sync-nightly-full` schedule
  rows.

The documents themselves and their stored files are not touched.

## Consequences

- `apps/drive` stays installed as a shell holding only its migrations,
  so that `0005` can run. A later release deletes the package, with its
  entry in `INSTALLED_APPS` and in the import-linter contracts.
- Where a document came from is no longer recorded. Back up the
  database before migrating if the Drive provenance matters.
- No new draft can be linked until the Dropbox integration provides a
  way to pick the file. Users of existing links keep their extension;
  it downloads from `/case/drafts/companion/kosmos-companion.oxt`.
- A renamed draft file no longer pairs with its link: the link's name
  was refreshed from Drive, and nothing refreshes it now.
- The mirror's design (append-only, PDF-only, tombstones, folder to
  category mappings keyed by folder id, never suggesting Evidence) is in
  git history and in the superseded records below. It is the reference
  for the Dropbox mirror.
- A `drive_tokens.json` left in `GOOGLE_DATA_DIR` is no longer read and
  can be deleted.

## Related

- [The Drive mirror: append-only, PDF-only, read-only on Drive
  (2026-08-01)](2026-08-01-drive-mirror-contract.md) and [Drive folder
  mappings replace the per-proceeding folder link
  (2026-08-21)](2026-08-21-drive-folder-mappings-replace-proceeding-folders.md):
  the records this one supersedes.
- [Drafts are companion-first over a Drive `.odt`
  (2026-08-06)](2026-08-06-drafts-are-companion-first.md), [Closing a
  matter unlinks its mirrors and starts the chat clock
  (2026-08-01)](2026-08-01-closing-a-matter-unlinks-mirrors-and-starts-the-chat-clock.md)
  and [The case builder is a module with its own navigation
  (2026-10-19)](2026-10-19-the-case-builder-is-a-module-with-its-own-navigation.md):
  superseded in part.
- [Notes are retired (2026-10-27)](2026-10-27-notes-retired.md).
- [Firm files live in Dropbox, and the AI reads them in place
  (2026-10-29)](2026-10-29-firm-files-live-in-dropbox.md): what was built
  against Dropbox. Not a mirror; the mirror's design above is history.
- [Drafts](../dev/subsystems/drafts.md), [Case
  building](../dev/subsystems/case-building.md) and [Drafting with
  LibreOffice](../admin/integrations/libreoffice.md).
