# MCP server and JSON APIs

Claude Desktop reaches Kosmos through a small MCP server that each user
runs on their own machine, talking to token-authenticated JSON APIs in
`apps/notes`, `apps/case` and `apps/search`. User-facing setup is in the
operator guide: [Claude Desktop access to Kosmos](../../admin/integrations/claude-desktop.md).

Access is per user: requests authenticate with the same `CompanionToken`
the LibreOffice companion uses (header `X-Kosmos-Token`), so a user's
Claude sees exactly what that user can see, and deactivating the user
kills the token.

## Where the code is

| Module | Holds |
|---|---|
| `tools/kosmos_notes_mcp.py` | The stdio MCP server Claude Desktop launches; one tool per API call |
| `apps/drafts/api_auth.py` | `kosmos_api_auth`, the token decorator that sets `request.api_user` |
| `apps/notes/api.py` | Matter list, note manifests, note read and the gated note write, note search |
| `apps/case/api.py` | A matter's sections as AI-ready text, documents, email threads, conversations, invoices, hybrid search, the three write endpoints |
| `apps/search/api.py` | Practice-wide search, as the search page does it |
| `apps/settings/claude/views.py` | Settings → Claude Desktop: the config block, script download, rotate and revoke |
| `apps/case/ai/context.py` | The section formatters the matter API reuses |

## Data model

`CompanionToken` (`apps/drafts/models.py`) is one row per user
(`OneToOneField`, `CASCADE`) with a unique `key`. There is no separate MCP
token: rotating the key from the Claude Desktop page re-keys the
LibreOffice companion too. `Note.ai_write_until` is the per-note write
grant (below).

## The three pieces

- **JSON APIs** (every view wrapped in `kosmos_api_auth`):
  - `apps/notes/api.py`, under `notes/api/`: `matters/?q=`, `notes/?scope=`,
    `notes/<id>/`, `search/?q=&scope=&limit=` (default 20 per band, max
    100), and the one note write path `notes/<id>/write/` (POST append or
    replace, gated per note by `Note.ai_write_until`). Scopes are
    `all | library | matters | matter:<id>`, restricted to open matters.
    Ranking and scope parsing are shared with the Ctrl+K palette so the
    two surfaces cannot drift.
  - `apps/case/api.py`, under `case/api/`: `matter/<id>/<section>/` serves
    the sixteen `SECTIONS` as AI-ready text (overview, contacts, rates,
    activity, events, tasks, proceedings, settlement, documents,
    highlights, timeline, witnesses, emails, conversations, ledger,
    trust), reusing the in-app chat's formatters from
    `apps/case/ai/context.py` where they exist; `documents/<id>/`,
    `matter/<id>/emails/<thread_id>/`, `matter/<id>/conversations/<id>/`
    and `invoices/<id>/` serve full content; `matter/<id>/search/` runs
    the agent's own `search_materials` handler so ranking is identical;
    POSTs to `matter/<id>/facts/`, `matter/<id>/witnesses/` and `tasks/`
    create rows through the same validated entry creators the in-app AI's
    fenced blocks use.
  - `apps/search/api.py`, under `search/api/`: the practice-wide search
    (matters of any status, proceedings, contacts, intakes, notes) as
    manifest lines with handles.
- **MCP server** (`tools/kosmos_notes_mcp.py`): a single-file stdio
  translator on the mcp SDK's `MCPServer` that Claude Desktop launches
  itself. Tools: `find_matter`, `list_library`, `list_matter_notes`,
  `search_notes`, `read_note`, `write_note`, `read_matter`,
  `search_matter`, `search_kosmos`, `read_document`, `read_email_thread`,
  `read_conversation`, `read_invoice`, `add_fact`, `add_witness`,
  `add_task`. Long reads truncate at `READ_TRUNCATE_CHARS` (40k) with an
  explicit marker. All intelligence lives in the APIs; the script only
  formats, so a port to another runtime stays trivial.
- **Settings page** (Settings → Claude Desktop, `apps/settings/claude/`):
  renders the exact `claude_desktop_config.json` block with the user's
  real token substituted (the `.oxt` precedent, generalized), serves the
  script for download, and offers rotate and revoke.

## Access

Matters are the user's accessible open matters only, through
`filter_matters_for_user()`, and every denial of a matter, document,
thread or conversation is a 404 so it does not confirm existence. The
money sections (`FINANCIAL_SECTIONS`: rates, ledger, trust) and invoice
reads additionally need `has_financial_access()` (admin or
`perm_financial`), like the in-app Rates and Ledger tabs; that denial is a
403, since the matter's existence is already known to the caller. The
activity section is open to every user who can see the matter, as the
Activity screens are. Intakes in the practice-wide search need
`perm_intakes`. Inactive users are refused at the token check. See the
[permissions reference](../../reference/permissions.md).

## Write access

Three write surfaces, all create-or-append, none destructive:

- **Notes**: `write_note` appends to (default) or replaces one note's
  markdown. It works only while that note's AI button in the editor
  toolbar (the sparkles icon) is switched on: a per-note grant stored as
  a 24-hour expiry timestamp (`Note.ai_write_until`), toggled off by a
  second click and self-expiring otherwise. The grant is per note and
  note-wide (any user's Claude with access to the note may write while it
  is on), because the MCP API is stateless token auth: there is no
  browser session to consult, so the note itself carries the grant.
  Writes land in the note's history like any other edit, and an open
  editor detects them through the normal conflict machinery. Claude
  cannot create or delete notes. The in-app AI's note writes are not
  gated by this field (see [AI chat and context](ai/context.md)).
- **Timeline facts and witnesses**: `add_fact` and `add_witness` reuse
  `_create_fact_from_entry()` and `_create_witness_from_entry()`
  (validation, matter scoping of cited ids, name dedup): exactly what the
  in-app chat's fenced blocks can do, no more.
- **Tasks**: `add_task` reuses `create_task_from_ai_entry()`, assigned to
  the token's user; the API authorizes the matter itself, because the
  service resolves by name without an access check, and re-points the
  task after creation in case a duplicate name resolved elsewhere.

## Things that bite

- **The formatters are shared on purpose.** A change to a section
  formatter in `apps/case/ai/context.py` changes what both the in-app chat
  and Claude Desktop see; a new section needs a `SECTIONS` entry and, if
  it carries money, a place in `FINANCIAL_SECTIONS`.
- **Matter scope differs by API.** The notes and case APIs serve open
  matters only; the practice-wide search lists matters of any status,
  because it is navigational.
- **The script is the shipped artefact.** Users download it from the
  settings page and run it with `uv`; a change to a tool's signature or
  docstring reaches them only after they re-download.
- **Email threads list most-recent-activity first** (2026-09-25), so the
  40k truncation drops the oldest; keep that order when touching
  `_format_email_threads()`.

Where the transport and packaging may go next is recorded in
[Claude Desktop: packaging roadmap](../../decisions/claude-desktop-roadmap.md).

## Related

- [Claude Desktop access to Kosmos](../../admin/integrations/claude-desktop.md)
  for setup; [AI chat and context](ai/context.md) and
  [Agentic chat](ai/agent-chat.md) for the formatters and the search
  handler this reuses; [Notes and drafts](notes-and-drafts.md) for the
  editor toggle and the companion token.
