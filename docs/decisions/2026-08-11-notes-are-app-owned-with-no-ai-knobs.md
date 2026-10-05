# Notes are app-owned and carry no AI knobs (2026-08-11)

Notes reached the application two ways in mid-2026. Since June a Drive
mirror pulled files from a `Notes/` folder under each matter's Drive
folder into `Note` rows, read-only in the editor because Drive was the
source of truth. In August the standalone editor grew into the notes'
home (folder trees, a Matters pane, drag-and-drop, context menus), and
on 2026-08-09 a firm Library was wired into the AI: a flag on a folder
made its notes selectable, and each note carried an `ai_context` setting
(auto, always, never) like a document. Two days later, on one day, both
arrangements were taken apart.

## Decision

Notes belong to the application. The Drive notes mirror is retired:
files under `Notes/` are ignored by the sync, the previously imported
notes are editable like any other, and `Note` has no Drive provenance
fields. The editor is the only place a note is written, by a person or by
the AI's note blocks.

Notes carry no AI settings. Every Library note (a note on no matter) is
selectable for the AI on every matter (`get_library_notes()`), every
matter note is selectable for its matter, and the way to force a note
into a conversation is to paste it. `NoteFolder.ai_library` and
`Note.ai_context` are gone (migration 0023 in `apps/notes`).

A later instance of the same stance: the Library tab's drag-and-drop and
right-click menus (2026-08-23) are a layer of their own over the tab's
folder sidebar and table, sharing the editor tree's server endpoints and
validation but not its code, because the editor tree navigates (a click
opens a note) and the sidebar filters the table.

## Alternatives

- **Drive as the notes' source of truth** (feat(drive): sync Google
  Drive case notes into the database, 2026-06-08): "One-way, read-only
  (Drive is the source of truth)." Retired on 2026-08-11; the module
  docstring records the outcome, "Notes are app-owned now", and the
  commit subject the effect, "unlock imported notes". No fuller reason
  is recorded; the same day's commits made the editor self-sufficient
  (launcher, recents, properties, trees), which a read-only mirrored
  note could not take part in.
- **An AI-library flag per folder plus a per-note setting** lived from
  2026-08-09 to 2026-08-11. Replaced by "whole library is selectable";
  the commit carries no body, and the model docstring gives the rule
  that replaced it. The selector, not a flag, decides what is relevant.
- **Reusing the editor's file tree on the Library tab** for drag-and-
  drop: not done, on purpose, per the comment heading
  `static/js/notes-library.js`.

## Consequences

- Do not add an AI toggle to notes or folders. Relevance is the
  selector's job (it is told to pick at most five library notes and only
  when the topic bears on the question), and the auto-summary opts out
  of the library altogether.
- Do not rebuild a Drive mirror for notes. `apps/drive/google.py` keeps
  skipping the `Notes/` folder through `is_hidden_folder()` so a legacy
  tree never syncs as documents either.
- Library notes feed the AI through their summaries
  (`generate_note_summary`, Library notes only); matter notes go in
  whole. A note that must never reach the AI has no switch; it should
  not be a note.
- The Library tab and the editor tree change independently. A move or
  reparent rule lives on the server (`validate_folder_move()`,
  `note_move`) so both layers get it.

## Evidence

- `apps/notes/models.py`, `get_library_notes()` docstring: "Notes carry
  no AI knobs: library notes are all selectable, matter notes are all
  selectable for their matter, and force-inclusion is copy-paste into
  the chat."
- `apps/drive/google.py`, module docstring: "RETIRED: the case-notes
  mirror (2026-08-11; files under ``Notes/`` are ignored)";
  `is_hidden_folder()`.
- `apps/notes/migrations/0023_remove_historicalnote_ai_context_and_more.py`.
- `static/js/notes-library.js`, header comment: "A library-specific
  layer on purpose: the editor's tree is a navigator (click opens), this
  sidebar is a filter for the table."
- Commits: "feat(drive): sync Google Drive case notes into the database"
  (2026-06-08); "feat(notes): AI library flag on folders, AI summary
  fields on notes" (2026-08-09); "feat(notes): retire Drive notes mirror,
  unlock imported notes", "refactor(notes): drop Drive provenance fields
  from Note", "refactor(notes): notes carry no AI knobs" (all
  2026-08-11); "feat(notes): Library tab drag-and-drop + right-click
  menus" (2026-08-23).

## Related

- [Notes and drafts](../dev/subsystems/notes-and-drafts.md), "Trees,
  the Library and the matter tab" and "Retired designs".
- [AI chat and context](../dev/subsystems/ai/context.md), "What goes
  into the context".
- [AI writes are fenced blocks, applied at
  once](2026-08-09-fenced-write-blocks.md).
- [The Drive mirror: append-only, PDF-only, read-only on
  Drive](2026-08-01-drive-mirror-contract.md).
