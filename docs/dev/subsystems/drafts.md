# Drafts

A draft is a `.odt` file, opened in LibreOffice Writer, that a case AI
conversation is pinned to so the AI can read it and propose tracked
changes through a companion extension. Drafts are `apps/drafts` over the
case AI chat.

Linking a new draft is off. The link was made by picking an `.odt` from
the matter's Google Drive folder, and with Google Drive removed there is
no picker until the Dropbox integration gives the server a way to list
the files (see [Google Drive is
removed](../../decisions/2026-10-27-google-drive-removed.md)). Existing
links keep working through the companion as described here.

## Where the code is

| Path | What it holds |
|---|---|
| `apps/drafts/models.py` | `DraftLink`, `CompanionRound` |
| `apps/accounts/models.py`, `apps/accounts/api_auth.py` | `ApiToken` (formerly `drafts.CompanionToken`, same table) and `kosmos_api_auth` |
| `apps/drafts/chat.py` | The draft section of the AI context and the edit rounds |
| `apps/drafts/companion.py` | The API the extension polls, and the `.oxt` build |
| `apps/drafts/companion_src/` | The LibreOffice extension (`kosmos_companion.py`, `description.xml`, `Addons.xcu`) |
| `apps/drafts/views.py`, `templates/ai/draft-chip.html`, `templates/ai/companion-setup.html` | The chip (an existing link, its companion-setup button and its unlink button) and the setup modal |
| `utils/convert.py` | ODT to Markdown through pandoc (shared with mail attachments) |
| `apps/drafts/redline.py`, `apps/drafts/uno_driver.py` | The headless redline driver, dormant (see below) |

## Data model

- **`DraftLink`**: one-to-one on a case `Conversation` (CASCADE),
  `drive_file_id` (the file's identity, kept from the Drive picker; the
  companion API's `file` field), `name`, `doc_text` (the Markdown facsimile the AI
  reads), `doc_text_at`, `companion_seen`. `sibling_links()` are the
  links to the same file by the same user; `companion_active` is true
  when any sibling was polled in the last 15 seconds.
- **`ApiToken`** (in `apps/accounts`): one per user, the `X-Kosmos-Token`
  key the extension and the MCP server both send.
- **`CompanionRound`**: one AI edit round, `edits` (wire dicts from
  `apps.drafts.redline.edit_to_dict`), `status` (pending, applied, failed,
  expired), `delivered_at`, `result`, `error`, `edit_index`.

## How it works

### Companion-first

Drafts exist only with AI configured: the link routes live under
`/case/ai/` and the companion's setup, download and API under
`/case/drafts/`, and `PermissionMiddleware` answers 404 on both while
`ai_enabled()` is false (see
[AI is optional](ai/context.md#ai-is-optional)).

The design, stated in `apps/drafts/models.py`: there is no server-side
working copy, no version chain and no publish step. The document in
Writer is the working copy, Ctrl+Z is version control, and saving the
file is publishing.

1. **Link.** An existing `DraftLink` shows as a chip in the chat
   composer (`draft-chip.html`) with an unlink button
   (`draft_unlink`). No view creates one; an unlinked conversation shows
   no draft button.
2. **Context.** When the conversation has a link, the chat worker
   appends `chat.build_draft_section()` to the system prompt: the
   preamble, the edit protocol and the draft text. The text is
   `doc_text` as the companion last pushed it; nothing re-fetches it.
   The link's `name` never changes, and the extension pairs by file
   name, so a renamed file no longer pairs.
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
`ApiToken`. `EXTENSION_VERSION` in `companion.py` and
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
  (`apps/drafts/redline.py`, `uno_driver.py`) stays, dormant and tested,
  for a future server-side write-back path.
- **Canvas mode** (branch `feat/drafting-canvas`, 2026-08-07 to 08-09,
  never merged): a second draft surface whose text lived in `doc_text`
  itself with a TipTap pane in the chat window; pruned without merging.

## Background work

Drafts queue no tasks of their own. The edit round wait runs inside the
AI chat task on the worker, and drafts have no schedule; see
[Scheduled jobs](../../reference/schedules.md).

## Access

The companion API authenticates by token and re-checks matter
membership on every call (`_user_links()` for the listing, `_get_link()`
for a link, which answers 403 for a lost matter and 404 for an unlinked
draft), since a user taken off a matter keeps their token; the draft
views under `/case/ai/conversations/<conv_id>/draft/` rely on the
middleware plus `_get_conversation()`, which excludes matter-less
conversations. The permission matrix is in the
[permissions reference](../../reference/permissions.md).

## Things that bite

- **Rounds are never redelivered and `doc_text` is shared across
  sibling links.** A query on `CompanionRound` or `DraftLink` for one
  file must go through `sibling_links()`, or two conversations on one
  document disagree about what was applied.
- **The companion protocol only grows.** A change that breaks the
  0.3.0 sequence breaks installed extensions until every user downloads
  again; `test_round_lifecycle.py`'s 0.3.0 class is the guard.

## Related

- Guide: [Drafts](../../guide/drafts.md), [AI chat](../../guide/ai-chat.md)
- Admin: [Drafting with LibreOffice](../../admin/integrations/libreoffice.md)
- Subsystems: [AI context](ai/context.md), [Agent chat](ai/agent-chat.md)
- Conventions: [Testing](../conventions/testing.md)
