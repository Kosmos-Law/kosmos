# The Drive mirror: append-only, PDF-only, read-only on Drive (2026-08-01)

A firm files its record in Google Drive by hand, and the application
needs those files as `Document` rows (OCR'd, searchable, highlightable,
visible to the AI). A sync that mirrors a folder tree has to decide what
happens when a file is deleted, trashed or moved on the Drive side,
which files it takes, and whether the application ever writes back. The
record-folder mirror of 2026-08-01 fixed those three answers, and every
later change to the mirror has kept them.

## Decision

- **Append-only.** A deletion, trash or move out of a mapped folder on
  Drive never removes a `Document`. The record shrinks only through a
  deliberate delete in the application, which writes a
  `DriveRecordTombstone` for the file id (a `pre_delete` signal) so the
  file does not come back on the next pass.
- **PDFs only.** Anything else under a mapped folder is counted, not
  ingested.
- **Read-only on Drive.** The application never writes to Drive; the
  OAuth scope it asks for is `drive.readonly`. A modified file is
  refreshed (bytes replaced, OCR reset); user-set metadata is never
  touched after the first ingest.

Two rules follow. A document that came from Drive cannot be moved to
another matter in the application, because the next sync would move it
straight back: Edit Details locks its Matter field and a bulk move skips
it (2026-10-02). And `suggest_mapping()` never pre-fills Evidence for a
folder, whatever it is called: Save posts every row of the mapping
table, a firm's Evidence folder is typically the bulk pile, and a
pre-filled Evidence would be mapped by a user who only came to map
correspondence (2026-08-21).

## Alternatives

- **A mirror that deletes.** The retired notes mirror did delete a note
  when its Drive file vanished; the record mirror never did ("the record
  sync is append-only by design", feat(drive): record-sync schema,
  2026-08-01). The commit states the rule, not the reasoning; the
  tombstone is what makes it workable.
- **The "Key Documents" convention** (2026-08-01 to 2026-08-21): any
  folder of that name, at any depth, synced its PDFs as curated
  Evidence with no configuration. Replaced by the Drive Folder modal,
  which maps top-level subfolders to a category and proceeding by
  folder id; legacy nested Key Documents rows were converted into
  mappings by data migration and keep syncing until unmapped. The
  convention is not re-suggested by name.
- **Writing back to Drive**: unbuilt. The headless redline driver is
  kept dormant for a future write-back path; nothing writes today.

## Consequences

- Do not add a delete path to the sync. Delete in the application;
  the tombstone handles the rest. `drive_file_id` is unique, which is
  what makes the upsert safe under two concurrent passes.
- Moving a Drive document means moving the file in Drive. A new move
  path in the application (a bulk action, an API) must check
  `drive_file_id` and refuse as `documents_edit` does.
- Closing a matter clears its Drive link and mappings; the synced
  documents stay.
- A new folder-name convention in `suggest_mapping()` must not
  pre-fill Evidence.
- A Drive feature that needs a write scope widens the OAuth consent
  for every firm; that is a decision to record, not a line to change.

## Evidence

- `apps/drive/records.py`, module docstring, under "Contract":
  "Append-only. Drive-side deletions, trashes and moves NEVER remove a
  Document; the record can only shrink through a deliberate in-app
  delete, which tombstones the Drive file id."
- `apps/drive/signals.py`, `tombstone_synced_record()`.
- `apps/drive/mappings.py`, the comment above `_NAME_TO_CATEGORY`:
  "Evidence is deliberately NOT suggested."
- `apps/drive/google.py`, module docstring: "RETIRED: ... the
  zero-config "Key Documents" convention (2026-08-21)".
- `apps/case/documents/views.py`, `DRIVE_MOVE_MESSAGE`: "The sync would
  move it straight back, so it is not moved here."
- `apps/settings/integrations/views.py`: the `drive.readonly` scope.
- Commits: "feat(drive): record-sync schema", "feat(drive):
  record-folder ingest engine" and "feat(drive): Key Documents folders
  sync as curated Evidence" (2026-08-01); "feat(drive): one Drive Folder
  workflow mapping subfolders to categories and proceedings" and
  "feat(drive): never suggest Evidence; mapping the evidence pile is a
  by-hand choice" (2026-08-21); "fix(documents): bulk actions stay on
  the matter, moves leave the old matter's labels behind, and a Drive
  document cannot be moved" (2026-10-02).

## Related

- [Case building](../dev/subsystems/case-building.md), "The Drive
  mirror".
- [Google Workspace](../admin/integrations/google.md) for the
  connection.
- [Notes are app-owned and carry no AI
  knobs](2026-08-11-notes-are-app-owned-with-no-ai-knobs.md): the notes
  mirror that was retired.
- [Drafts are companion-first over a Drive
  `.odt`](2026-08-06-drafts-are-companion-first.md): why the server does
  not save the draft to Drive.
