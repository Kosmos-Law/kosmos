# Closing a matter unlinks its mirrors and starts the chat clock (2026-08-01)

A matter's documents mirror in from a Google Drive folder and its emails
from a Gmail label, both under roots named for open matters. When a firm
closes a file it moves the Drive folder and the Gmail label to a closed
root, and a matter that still pointed at the old names produced
missing-folder and missing-label warnings on every sync; worse, the
automatic label setup recreated the matter's label in every mailbox.
Separately, AI chat conversations and their message history were
accumulating on matters nobody would open again, and the history rows
were the bulk of the table.

## Decision

Two rules, both keyed on the matter's status:

- On every save whose status is in `Matter.INACTIVE_STATUSES` (`Complete`
  or `Closed`), `Matter.save()` clears `drive_folder`, `drive_folder_id`
  and `gmail_label_name` and deletes the matter's `DriveFolderMapping` and
  `DriveMatterState` rows. Nothing synced is removed: record documents
  are append-only and email rows are only removed by label events on a
  matter that still has a label. Reopening does not relink; the user maps
  the folder again.
- `Closed`, and only `Closed`, starts a retention clock.
  `apps/case/ai/purge.py` deletes a matter's AI conversations, messages
  and their history rows once it has been Closed for
  `CHAT_RETENTION_DAYS` (180; `0` switches the purge off). `closed_at()`
  reads the simple-history rows newest-first and takes the start of the
  latest unbroken run of `Closed`, so a matter reopened and closed again
  counts from the second closing. Chats are working notes, not part of
  the client file; the file lives in Drive, Gmail and the notes.

`Complete` is the closing-out phase (work has ended, usually waiting on a
trust reimbursement); its Drive folder has already moved, so it gets the
unlink but not the purge.

## Alternatives

Leaving the links in place and tolerating the warnings was the state
before 2026-08-01. Counting retention from the first closing, or from
`date_end`, would purge a reopened matter's chats on the old schedule;
the streak rule was chosen so that reopening restarts the clock. The
reason `Complete` does not start the clock is not recorded beyond its
being "not final".

## Consequences

- A status change through any path (the form, the Overview dropdown)
  unlinks the mirrors; a `queryset.update()` skips `save()` and does not.
- The purge reads history. A matter whose history holds no `Closed` row
  is never purged, and `clean_history` with a short window changes what
  the purge sees.
- The purge is a weekly schedule (`chat-purge-weekly`, Sunday 03:00) and
  nothing is marked: an aborted run is recomputed from scratch next week.
- Migration `matters 0053` applied the unlink to matters already
  Complete; migration `0054` later filled `date_end` from history.

## Evidence

- Commit "feat(matters): close cleanup - auto-unlink mirrors + chat
  sunset" (2026-08-01): "closed files leave the Matters - Open roots, so
  stale links only generate drift warnings, and automatic label setup
  would recreate closed matters' labels ... counting from the latest
  Closed streak so reopened matters restart the clock."
- Commit "feat(matters): Complete matters drop their Drive and Gmail
  mirrors like Closed ones" (2026-08-21): "Chat retention still keys off
  Closed only."
- `Matter.save()` in `apps/matters/models.py`, the comment beginning
  "Drop the matter's Drive folder mappings along with its Drive and Gmail
  links", and the comment on `INACTIVE_STATUSES`.
- `apps/case/ai/purge.py`, module docstring ("Chats are working notes,
  not part of the client file") and `closed_at()`.
- `CHAT_RETENTION_DAYS` became an environment variable in "fix: close the
  operator gaps the documentation audit found" (2026-10-01).

## Related

- [Matters, contacts and parties](../dev/subsystems/matters.md): Closing,
  reopening and the chat purge.
- [Email and intakes](../dev/subsystems/email-and-intakes.md): what a
  label-less matter keeps.
- [Gmail mirror](2026-07-31-gmail-mirror-per-user-mailboxes.md).
