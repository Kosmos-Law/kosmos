# Claude Desktop access to Kosmos

Claude Desktop on a user's own machine can work with Kosmos directly:
read the notes Library and, for any open matter the user can access, the
full record (notes, contacts, rates, activity, events, tasks,
proceedings, settlement, documents, highlights, timeline, witnesses,
synced emails). Writes are narrow and deliberate: append/replace on
notes whose editor AI-write toggle is on, and create-only timeline
facts, witnesses, and tasks. Access is per-user: it authenticates with
the same `CompanionToken` the LibreOffice companion uses (header
`X-Kosmos-Token`), so a user's Claude sees exactly what that user can
see, and deactivating the user kills the token.

Nothing needs configuring on the server. Each user sets up their own
machine from **Settings → Claude Desktop**. How the pieces fit together is
in the developer guide: [MCP server and JSON APIs](../../dev/subsystems/mcp.md).

## User setup

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
2. In Kosmos: Settings → Claude Desktop → download `kosmos_notes_mcp.py`,
   save it somewhere permanent.
3. In Claude Desktop: Settings → Developer → Edit Config. This opens
   `claude_desktop_config.json`. Note this is Claude **Desktop's**
   config, not Claude Code's `CLAUDE.md`/`.mcp.json`, and Desktop
   pre-populates it with defaults. The block on the Kosmos settings page
   is the `"mcpServers"` member only: paste it inside the file's
   outermost braces as an additional top-level entry (comma after the
   preceding entry), keeping what's already there, then fix the script
   path. If an `mcpServers` section already exists, add just the
   `"kosmos"` entry inside it.
4. Restart Claude Desktop; the kosmos tools appear under the tools icon in
   the chat input.

The settings page also offers rotate and revoke. Rotating re-keys the
LibreOffice companion too, because both use the same token.

## Scoping a Desktop Project to a matter

Desktop's MCP config is global: a Project cannot launch a different
server or pass different env. Matter scoping is conversational: the tools
take the matter as a parameter, and a per-matter Desktop Project carries
it in its custom instructions, e.g.:

> This project concerns the Kosmos matter "Rivera v. Northside Logistics".
> Resolve it once with find_matter, then pass its matter_id to the
> read_matter, search_notes, and add_fact tools.

The Library is available in every conversation, which matches its purpose.

## What Claude can write

Three write surfaces, all create-or-append, none destructive:

- **Notes**: Claude can append to (default) or replace one note's
  content, but only while that note's AI button in the editor toolbar
  (the sparkles icon) is switched on. The grant lasts 24 hours, is
  switched off by a second click, and applies to the note for any user's
  Claude that can access it. Writes land in the note's history like any
  other edit. Claude cannot create or delete notes.
- **Timeline facts and witnesses**: Claude can add them to a matter, with
  the same validation the in-app chat applies.
- **Tasks**: Claude can add tasks, assigned to the token's user.
