# Notes are retired (2026-10-27)

Kosmos had notes in two places. The firm-wide **Library** was a sidebar
entry over a tree of note folders, with an Inbox for unfiled notes, a
Ctrl+K palette and a rich-text editor that opened in its own browser
tab; the editor carried reference chips to documents and highlights, an
AI-write toggle and, for library notes, an AI summary written on the
queue. Each matter's case file had a **Notes** tab over the same model,
scoped to that matter. Notes were searchable firm-wide and inside a
matter, took labels, were embedded in the semantic index, and were read
and written by the AI: the context selector offered matter and library
notes, the agent searched them and read them with `read_note`, and the
fenced `create-note` and `edit-note` blocks wrote them. The Claude
Desktop connector listed, searched, read and wrote them too.

## Decision

The notes feature is retired, the Library and the matter Notes tab
alike. The firm decided to remove it. The case file's documents,
highlights, timeline and witnesses, and the AI chat, carry the working
record of a matter.

The data is kept. `apps.notes` stays installed with its models and
migrations only, dormant: nothing reads or writes the `Note`,
`NoteFolder` and `NoteView` tables. They stay registered so that Django's
cascade still deletes a matter's notes with the matter and a user's note
views with the user, and deleting either keeps working.

## What was removed

- The Library: its sidebar entry, the `/notes/` pages, note folders and
  the Inbox, the palette, the standalone editor and its AI-write toggle,
  reference chips in notes, library summaries with their tasks and the
  `backfill_note_summaries` command.
- The case file's Notes tab and every matter-scoped note route.
- The Library switch in Settings > Features (`Firm.library_enabled`);
  the Case file and Books switches stay.
- Notes as a kind in the firm-wide search and in case search, whose
  scopes are now documents, highlights and facts.
- Labels on notes.
- Notes in the AI: matter and library notes in the chat context and the
  selector's manifest, the `note` and `library` kinds of the agent's
  search, the `read_note` tool, the `[note:ID]` and `[lib:ID]` handles,
  and the fenced note-writing blocks (`apps/ai/note_blocks.py`). The AI
  still records timeline facts and witnesses.
- The `note` and `library` kinds of the semantic index.
- In the Claude Desktop connector (`tools/kosmos_notes_mcp.py`, which
  keeps its file name): the tools `list_library`, `list_matter_notes`,
  `search_notes`, `read_note` and `write_note`, and the notes JSON API
  under `/notes/api/`. `find_matter` stays, now served from
  `/case/api/matters/`.

## What the migration deletes

`apps/notes/migrations/0025_drop_note_index_rows.py` deletes the rows
derived from notes: the notes' chunks in the semantic index
(`MaterialChunk` rows of kind `note` and `library`) and their entries
in the watson keyword index. The notes themselves, their folders, their
views and their history rows are not touched.

## Consequences

- A copy of the connector script downloaded before this change calls
  endpoints that no longer exist. Each user downloads it again from
  Settings > Claude Desktop and restarts Claude Desktop.
- The note tables are dead weight until a later migration drops them,
  with `apps.notes` taken out of `INSTALLED_APPS` in the same change.
  Export the rows first if the firm wants them.
- Task notes, intake notes, the attorney notes on saved case law,
  contact notes and the notes fields on other records are separate
  fields and are not affected.

## Related

- [Notes are app-owned and carry no AI knobs (2026-08-11)](2026-08-11-notes-are-app-owned-with-no-ai-knobs.md)
  and [AI writes are fenced blocks, applied at once
  (2026-08-09)](2026-08-09-fenced-write-blocks.md): the records this
  one retires, in whole and in part.
- [The case builder is a module with its own
  navigation (2026-10-19)](2026-10-19-the-case-builder-is-a-module-with-its-own-navigation.md),
  which gave the Library its sidebar entry and its feature switch.
- [What deleting a matter or a contact removes (2026-10-02)](2026-10-02-what-deleting-a-matter-or-contact-removes.md).
- [Drafts](../dev/subsystems/drafts.md) and [MCP server and JSON
  APIs](../dev/subsystems/mcp.md).
