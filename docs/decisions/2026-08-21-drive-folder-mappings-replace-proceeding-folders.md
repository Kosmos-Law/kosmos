# Drive folder mappings replace the per-proceeding folder link (2026-08-21)

The Drive mirror turns PDFs in a matter's Google Drive folder into
Documents. Before August 2026 it found them three ways: the matter's own
folder was named on the matter, each proceeding carried a
`drive_folder` field naming the subfolder that held its court record,
and a zero-configuration convention filed anything under a "Key
Documents" folder as Evidence. Three links in three places, all by
folder name, so a rename in Drive broke the link, and the Documents tab
had no one place to see or change how the folder was read.

## Decision

A matter's Drive folder is mapped once, in the Drive Folder modal on the
Documents tab. The user picks the matter's folder and maps its top-level
subfolders to a category (Correspondence, Discovery, Evidence, Record)
and, for Record (required) or Discovery (optional), a proceeding. Each
mapping is a `DriveFolderMapping` row in `apps/drive/`, keyed by the
Drive folder id so a rename does not break it; the matter's folder is
likewise held as `Matter.drive_folder_id`. PDFs anywhere under a mapped
folder sync in with that row's category and proceeding (nearest mapped
ancestor wins). Unmapped folders are ignored. Name conventions only
pre-fill unsaved rows; nothing syncs until Save.

`Proceeding.drive_folder` and its constraint are gone (migration
`matters 0052`), and the "Key Documents" convention is retired. Migration
`drive 0004` converted the old name-based links into mapping rows.

## Alternatives

Keeping the proceeding field and adding mappings beside it would have
left two sources for a Record folder. Keeping "Key Documents" as an
implicit rule would have left one category with no visible mapping.
Both were converted rather than kept; legacy nested rows such as
`Evidence/Key Documents` were turned into mappings so they keep syncing
until someone unmaps them.

## Consequences

- A proceeding's Drive folder is a `DriveFolderMapping` with that
  proceeding, not a field on the proceeding. Deleting a proceeding
  unmaps its folders; they reappear as unmapped suggestions.
- Identity is the folder id. `folder_path` is a cached display value,
  refreshed when the folder is listed, and is never used to attach a
  document except once, in the conversion migration.
- Closing a matter deletes its mapping rows along with the folder link
  (see the closing record), so a reopened matter is mapped again.
- The mapping's category rules mirror `Document.save()`: Record needs a
  proceeding, Discovery may have one, Correspondence and Evidence never
  do. The check constraint `drive_folder_mapping_proceeding_rule` and
  the document rule must stay in step.

## Evidence

- Commit "feat(drive): one Drive Folder workflow mapping subfolders to
  categories and proceedings" (2026-08-21): "Replaces the matter-folder
  link, the per-proceeding record-folder link and the zero-config Key
  Documents convention with a single modal on the Documents tab ...
  Proceeding.drive_folder and its constraint removed."
- `DriveFolderMapping` docstring in `apps/drive/models.py`: "Identity is
  the Drive folder id so renames in Drive do not break the link."
- `apps/drive/google.py` module docstring, the RETIRED paragraph dating
  the Key Documents convention's retirement to 2026-08-21.
- `apps/drive/migrations/0004_convert_legacy_links.py` and
  `apps/matters/migrations/0052_remove_proceeding_drive_folder.py`.

## Related

- [Case building](../dev/subsystems/case-building.md): the Drive mirror
  and the Drive Folder modal.
- [Matters, contacts and parties](../dev/subsystems/matters.md): the
  Proceeding model.
- [The Drive mirror: append-only, PDF-only, read-only on Drive](2026-08-01-drive-mirror-contract.md):
  the sync rules the mappings feed, and the Key Documents convention's
  place in them.
- [Closing a matter unlinks its mirrors](2026-08-01-closing-a-matter-unlinks-mirrors-and-starts-the-chat-clock.md).
