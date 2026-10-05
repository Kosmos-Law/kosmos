# Notes and drafts

Notes are Markdown documents in a folder tree: the firm's Library (notes
on no matter) and one private tree per matter, edited in one standalone
editor. Drafts are different: a draft is a `.odt` file in the matter's
Google Drive folder, opened in LibreOffice Writer, that a case AI
conversation is pinned to so the AI can read it and propose tracked
changes through a companion extension. Notes span `apps/notes` and
`apps/case/notes`; drafts are `apps/drafts` over `apps/drive` and the case
AI chat.

## Where the code is

| Path | What it holds |
|---|---|
| `apps/notes/models.py` | `Note`, `NoteFolder`, `NoteView` |
| `apps/notes/views.py` | The Library tab, the editor and its partials, folder CRUD, moves, autosave |
| `apps/notes/access.py` | Who may reach a note or folder (`note_for_user`, `visible_notes_q`) |
| `apps/notes/api.py` | Token-authed JSON API for the MCP server |
| `apps/notes/tasks.py` | AI abstracts for library notes |
| `apps/case/notes/` | The matter's Notes tab (list, filters, instant create, rename) |
| `apps/case/notes/markdown_ext.py` | Renders `[[doc:id|label]]` and `[[hl:id|label]]` references as links |
| `templates/notes/` | `editor.html` (the page), `editor-content.html` (the note partial), `editor-trees.html`, `main.html` (the Library tab) |
| `static/js/notes-editor.js` | Editor entry point: builds the TipTap editor, wires the modules |
| `static/js/notes/` | `markdown.js`, `autosave.js`, `broadcast.js`, `conflict-lock.js`, `file-tree.js`, `tab-state.js`, `references.js`, `tables.js`, `palette.js`, `outline.js`, `search.js` |
| `static/js/notes-library.js` | Drag-and-drop and context menus on the Library tab |
| `static/js/vendor/tiptap.bundle.js` | The TipTap bundle (see below) |
| `apps/notes/tests/js/` | Node tests for the editor modules |
| `apps/drafts/models.py` | `DraftLink`, `CompanionToken`, `CompanionRound` |
| `apps/drafts/services.py` | Drive listing, link creation, the stale refresh |
| `apps/drafts/chat.py` | The draft section of the AI context and the edit rounds |
| `apps/drafts/companion.py` | The API the extension polls, and the `.oxt` build |
| `apps/drafts/companion_src/` | The LibreOffice extension (`kosmos_companion.py`, `description.xml`, `Addons.xcu`) |
| `apps/drafts/views.py`, `templates/case/ai/draft-*.html` | The picker, the chip and the setup modal in the chat window |
| `apps/drive/convert.py` | ODT to Markdown through pandoc |
| `apps/drive/redline.py`, `apps/drive/uno_driver.py` | The headless redline driver, dormant (see below) |

## Data model

- **`NoteFolder`**: `name`, `parent` (SET_NULL), `matter` (CASCADE,
  nullable), `depth`. `matter` null is the general (Library) tree; set,
  it is that matter's private tree. `clean()` enforces four levels
  (`depth` up to 3), that a child is on the same matter as its parent,
  and no cycles; `save()` runs it unless `update_fields` is given.
- **`Note`**: `matter` (CASCADE, nullable; null means Library), `folder`
  (SET_NULL), `title`, `category`, `topic`, `content` (Markdown),
  `documents` and `highlights` as tracked sources, `labels`,
  `importance`, `summary` and `summary_source_hash` (the AI abstract),
  `ai_write_until`. History on every save. The invariant, stated on the
  field: `folder` is None or `folder.matter_id == matter_id`. It is
  enforced in the views (`validate_folder_move`, `note_move`), not in
  `clean()`, because every move path saves with `update_fields`.
- **`NoteView`**: one row per (user, note), `viewed_at`, for recents and
  `notes_launch`.
- **`DraftLink`**: one-to-one on a case `Conversation` (CASCADE),
  `drive_file_id`, `name`, `doc_text` (the Markdown facsimile the AI
  reads), `doc_text_at`, `companion_seen`. `sibling_links()` are the
  links to the same file by the same user; `companion_active` is true
  when any sibling was polled in the last 15 seconds.
- **`CompanionToken`**: one per user, the `X-Kosmos-Token` key the
  extension and the MCP server both send.
- **`CompanionRound`**: one AI edit round, `edits` (wire dicts from
  `apps.drive.redline.edit_to_dict`), `status` (pending, applied, failed,
  expired), `delivered_at`, `result`, `error`, `edit_index`.

## How it works

### Trees, the Library and the matter tab

One `NoteFolder.matter` column unifies the two kinds of tree, so the
editor's left panel renders both from one query: `get_editor_file_tree()`
builds the Files tree (general folders and notes) and a Matters pane with
one tree per Open matter the user may see, plus the seven most recent
notes. Every node renders collapsed; expansion, the active pane and tree
scroll are per browser tab in `sessionStorage` (`tab-state.js`), so two
tabs never move each other's tree.

The Library tab (`notes_index`, `templates/notes/main.html`) is a
different surface over the same data: its folder sidebar filters the
table of general notes (`get_notes_data`, session filters under
`standalone_notes_filter`). `notes-library.js` adds drag-and-drop and
right-click menus to it as its own layer; it shares the server endpoints
(`notes:folder-reparent`, `notes:note-move`, `notes:bulk-move`) with the
editor tree but not its code, because the editor tree navigates and the
sidebar filters. The matter's Notes tab (`apps/case/notes/views.py`) is
the same table for one matter's notes, inside the Case shell, with
instant create (`notes_add`) and a rename modal; per-note editing always
goes to the editor.

A move never crosses matters. `note_move` accepts a destination folder
only on the note's own matter, `note_folder_reparent` goes through
`validate_folder_move()`, and the one path that changes a note's matter,
`note_reassign_matter`, resets `folder` to None and suffixes the title if
the target root already has one. A same-named sibling at a destination
gets a serial suffix (`_next_untitled`) rather than blocking the move.

### The editor

`note_view` renders `templates/notes/editor.html`; switching notes swaps
`editor-content.html` in with HTMX (`note_content_partial`), which also
installs a fresh `window.NOTE_DATA` (ids, URLs, `updatedAt`, the AI-write
grant). `notes-editor.js` creates the TipTap editor from the modules it
imports and binds the toolbar, the trees, the Ctrl+K palette
(`notes_search_palette`, shared ranking with the API), the reference
picker (`references.js`, `reference_search`) and the outline.

`notes_launch` is where the Library's Editor button goes: the user's most
recently viewed note that is still within reach, else the newest visible
note. With no reachable note it renders `launch-empty.html`, a page with
a New note button (a POST to `notes_add`), rather than creating a note on
a GET. Background reloads call the partial with `?sync=1` so they do not
count as a view.

**Storage is Markdown, and the round trip is the risk.** The stored text
is plain text with Markdown marks; `markdown.js` turns it into editor HTML
(`markdownToHtml`) and back on every save (`htmlToMarkdown`), so anything
the first step mangles is written over the note two seconds later. The
loader escapes everything before it applies marks, lifts code spans,
reference chips and link addresses out first, and lets exactly one tag
through: a bare `<br>`, which is how a table cell breaks a line. What is
known to change shape, pinned by `markdown_roundtrip.test.mjs`: a
Markdown link becomes its text followed by the address in parentheses
(the editor has no link mark; an image reference `![alt](url)` is not a
link and stays as typed), underscores inside a word are never
emphasis, and table cells flatten to one line with literal pipes escaped
(but not the pipe inside a `[[doc:1|label]]` chip). Tables are GFM pipe
tables with outer pipes; column alignment round-trips through the
separator colons; resizing and merged cells are not offered because the
storage cannot hold them (`tables.js`).

**The TipTap bundle is built outside the repository.** The esbuild
project (`build.mjs`, `package.json`, `src/tiptap.js`) was removed on
2026-02-28 and the bundle is committed as an artifact. The recipe is in
the commit "feat(notes): table support with pipe-markdown round-trip"
(2026-08-15): `@tiptap/*@2.27.2`, esbuild with `format: esm`, minify,
sourcemap, target es2020, an entry that re-exports every name imported
from the bundle (grep `vendor/tiptap.bundle.js` under `static/js/`: the
editor, `references.js`, `conflict-lock.js`, `tables.js`, `search.js`,
`highlight-mark.js`, `plain-copy.js` and `prompt-editor.js`). Rebuild in
a scratch project and commit the new bundle and map.

### Saving and conflicts

`autosave.js` debounces two seconds, then POSTs `content` and
`base_version`, the exact `updated_at` isoformat string this tab last
received, to `note_autosave`. `_version_conflict()` in
`apps/notes/views.py` answers `409` when they differ: another tab, another
person or the AI saved since. `note_title` makes the same check. A `409`
puts the tab into conflict (`enterConflict`): editing is paused behind
the banner in `editor-content.html`, every control that would change the
note (`data-editing-only` in `editor.html`: the format toolbar and its
overflow items, Import, Replace, the table bar) is hidden, and
`ConflictLock` (`conflict-lock.js`, a ProseMirror plugin) refuses every
transaction that changes the document, because `setEditable(false)` stops
typing but not programmatic commands. Reload (`reloadNoteContent`) is
the only way out. A failed save retries three times; `pagehide` flushes a
dirty buffer with `keepalive`.

Tabs talk over a `BroadcastChannel` (`broadcast.js`): `note-saved`
carries the note id and new `updatedAt`, and a clean sibling tab on the
same note reloads silently while a dirty one enters conflict;
`tree-changed` makes siblings re-fetch the trees; `note-deleted` sends a
tab with that note open to `notes_launch`. `note_ai_write` saves with
`update_fields` so toggling the grant does not bump `updated_at` and
raise a false conflict. A save's answer is applied only if
`window.NOTE_DATA` is still the object the save was sent for
(`autosave_stale_response.test.mjs`), so a switch mid-save cannot stamp
one note's version onto another.

### The JSON API

`apps/notes/api.py` serves matters, note lists, one note, search and the
single write path, under `kosmos_api_auth`. `api_note_write` appends to
or replaces a note's Markdown only while `Note.ai_write_until` is in the
future; the editor's sparkles button (`note_ai_write`) grants 24 hours
and a second click clears it. The grant is per note and note-wide, since
token auth has no browser session to consult. The in-app AI's note
writes (`apps/case/ai/note_blocks.py`, fenced `create-note` and
`edit-note` blocks) are not gated by it. The API and the MCP server are
described in [MCP](mcp.md).

### Drafts: companion-first

The design, stated in `apps/drafts/models.py`: there is no server-side
working copy, no version chain and no publish step. The document in
Writer is the working copy, Ctrl+Z is version control, and saving the
file (which the user's Drive client syncs) is publishing.

1. **Link.** The pen button in the chat window opens `draft_picker`,
   which lists `.odt` files under the matter's Drive folder
   (`services.list_matter_odt_files`, walking subfolders to
   `MAX_LIST_DEPTH`, soft-failing to an empty list). `services.create_link()` refuses a file the picker
   would not have offered, fetches it, converts it with
   `convert.to_markdown()` (pandoc) and stores the text on a `DraftLink`.
2. **Context.** When the conversation has a link, the chat worker
   appends `chat.build_draft_section()` to the system prompt: the
   preamble, the edit protocol and the draft text. First it calls
   `services.refresh_if_stale()`, which re-fetches from Drive when
   `doc_text_at` is older than five minutes **and** no companion is
   connected; with a companion connected the pushes are fresher than
   Drive, so it never re-fetches. A rename in Drive is propagated to every
   link on that file, because the extension pairs by file name.
3. **Edits.** The AI answers with one fenced `draft-edits` block of
   replace, `delete_paragraph` and `insert_after` operations (optionally
   with `occurrence`). `chat.apply_edit_blocks()` parses it
   (`_parse_edit_block`; a malformed block stays as text and changes
   nothing), refuses it with instructions when no companion is active,
   and otherwise `_apply_via_companion()` creates a `CompanionRound` and
   blocks in `_wait_for_companion()`. Each block is replaced in the
   stored message by the outcome sentence.
4. **The companion.** The extension polls `api_ops` every 2.5 seconds;
   `api_ops` hands a pending round out once (`delivered_at` set by a
   conditional update, never redelivered, because a redelivery could
   apply the same edits twice). Version 0.4.0 then claims it
   (`api_result` with `{"claim": true}`), applies it as tracked changes by
   "Kosmos AI" inside one undo context, and reports the outcome with the
   document as ODT bytes; `_store_document()` converts the push and
   writes `doc_text` on the link and all its siblings.

Two clocks govern the wait, both in `apps/drafts/chat.py`: an
uncollected round expires after `COMPANION_WAIT_SECONDS` (30), and is
then never handed out, so "not applied" is true; a collected round gets
`COMPANION_APPLY_SECONDS` (90) from `delivered_at`, restarted by the
claim, with a hard ceiling of twice that. A report arriving after the
chat gave up is still recorded (the edits are in the document by then),
and the chat's wording distinguishes "not collected" from "collected,
not confirmed".

The extension is served as a personalized `.oxt` by `companion_oxt`:
`companion_src/` zipped as is, plus a generated `config.json` carrying
`PUBLIC_BASE_URL` (or the request's host) and the user's
`CompanionToken`. `EXTENSION_VERSION` in `companion.py` and
`description.xml` must agree; `test_companion` checks it. Setup for
users and servers is in [Drafting with
LibreOffice](../../admin/integrations/libreoffice.md).

**Two extension versions are in use.** A user's copy changes only when
they download again, so 0.3.0 (collects and applies at once, no claim)
and 0.4.0 must both keep working: no path, method or key 0.3.0 uses may
change, and anything new must be optional for the client.
`test_round_lifecycle.py` replays the 0.3.0 call sequence against the
current server; `test_companion_extension.py` loads
`kosmos_companion.py` with UNO stubbed and drives its round handling
against the real views.

### Retired designs

Recorded so nobody rebuilds them.

- **Drafts v1** (2026-08-04 to 2026-08-06): `DraftSession` and
  `DraftVersion`, a server-side redline chain with PDF preview, two
  publish modes, a Drafts tab and a standalone window. Deleted in
  "refactor(drafts): fold drafting into case AI chat, companion-first"
  (2026-08-06) after live testing showed the companion made it dead
  weight; migration 0003 dropped the tables. The headless driver
  (`redline.py`, `uno_driver.py`) stays, dormant and tested, for a future
  Drive write-back path.
- **Canvas mode** (branch `feat/drafting-canvas`, 2026-08-07 to 08-09,
  never merged): a second draft surface whose text lived in `doc_text`
  itself with a TipTap pane in the chat window; pruned without merging.
- **The Drive notes mirror** (retired 2026-08-11, "feat(notes): retire
  Drive notes mirror, unlock imported notes"): notes synced from a
  `Notes/` folder in Drive, read-only in the editor. `Note` lost its
  Drive fields; `apps/drive/google.py` still skips that folder.
- **The AI-library flag on folders** (2026-08-09 to 08-11): replaced by
  `get_library_notes()`, every Library note is selectable for the AI and
  notes carry no AI knobs.

## Background work

| Task | Queued by | On failure |
|---|---|---|
| `apps.notes.tasks.generate_note_summary` | `note_autosave` on a Library note (debounced two minutes through the cache), `backfill_note_summaries` | logged; the summary stays stale and is retried on the next save |
| `apps.notes.tasks.queue_stale_library_summaries` | `notes_bulk_move`, through `queue_library_summary_sweep()`; `backfill_note_summaries` | logged |

The edit round wait runs inside the AI chat task on the worker, not as a
task of its own. Drafts have no schedule; see
[Scheduled jobs](../../reference/schedules.md).

## Access

The `/notes/` routes are outside the middleware's `/case/` matter check,
so every view that takes a note, folder or matter id goes through
`apps/notes/access.py`: a note or folder with no matter is the Library and
every signed-in user may see it; one on a matter needs
`has_matter_access`, and a refusal is a `404`. `visible_notes_q()` scopes
recents, launch and search. The matter's Notes tab under `/case/` is
covered by the middleware (`note_id` is in `MATTER_LOOKUPS`). The
companion API authenticates by token and re-checks matter membership on
every call (`_user_links()` for the listing, `_get_link()` for a link,
which answers 403 for a lost matter and 404 for an unlinked draft), since
a user taken off a matter keeps their token; the draft views under `/case/ai/conversations/<conv_id>/draft/`
rely on the middleware plus `_get_conversation()`, which excludes
matter-less conversations. The permission matrix is in the
[permissions reference](../../reference/permissions.md).

## Things that bite

- **Every move path saves with `update_fields`, so `clean()` never
  runs.** A new move or reparent endpoint must call
  `validate_folder_move()` or make the same-matter check itself, or a
  note can end up in another matter's folder.
- **Anything that touches `updated_at` on a note someone has open
  raises a conflict banner.** Save metadata with `update_fields` as
  `note_ai_write` does; a content change should raise it, that is the
  point.
- **`markdown.js` is the schema.** A new TipTap node or mark that
  `htmlToMarkdown` cannot serialise is silently lost on the next
  autosave. Add the round trip and a case in
  `markdown_roundtrip.test.mjs` first.
- **The bundle's exports are the contract.** Importing a name from
  `tiptap.bundle.js` that the bundle does not export fails only at
  runtime, in the browser; the Node tests import the modules that avoid
  the bundle on purpose (`autosave.js`, `markdown.js`).
- **Rounds are never redelivered and `doc_text` is shared across
  sibling links.** A query on `CompanionRound` or `DraftLink` for one
  file must go through `sibling_links()`, or two conversations on one
  document disagree about what was applied.
- **The companion protocol only grows.** A change that breaks the
  0.3.0 sequence breaks installed extensions until every user downloads
  again; `test_round_lifecycle.py`'s 0.3.0 class is the guard.
- **The Library summary task is a no-op for matter notes.**
  `generate_note_summary` returns when `matter_id` is set; matter notes
  feed their matter's context whole.

## Related

- Guide: [Notes](../../guide/notes.md), [Drafts](../../guide/drafts.md),
  [AI chat](../../guide/ai-chat.md)
- Admin: [Drafting with LibreOffice](../../admin/integrations/libreoffice.md),
  [Claude Desktop](../../admin/integrations/claude-desktop.md),
  [Google Workspace](../../admin/integrations/google.md)
- Subsystems: [MCP](mcp.md), [AI context](ai/context.md),
  [Agent chat](ai/agent-chat.md), [Case building](case-building.md)
  (the Drive mirror, labels, the matter Notes tab's shell)
- Conventions: [HTMX and Alpine](../conventions/htmx-alpine.md),
  [Testing](../conventions/testing.md)
