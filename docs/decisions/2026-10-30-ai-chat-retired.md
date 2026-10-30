# The AI chat is retired

**Date:** 2026-10-30
**Status:** Accepted

## Context

[AI chat becomes Claude Code sessions](2026-10-29-ai-chat-becomes-claude-code-sessions.md)
rebuilt the matter chat on the Claude Agent SDK, and
[Firm files live in Dropbox](2026-10-29-firm-files-live-in-dropbox.md)
gave it the matter's folder to work in: a Dropbox daemon on the server,
a watcher that OCR'd PDFs in place, a per-matter folder link, and an
index of every document's text for the agent to search. It worked, and
it was a day old when the firm looked at what it already used.

The firm does its AI work in Claude's own apps. Those get better every
month without anything being built here: the desktop app's transcript,
its projects, its memory, its connectors. A chat inside Kosmos was a
second, smaller copy of that, with its own model list, its own effort
picker, its own rendering of what the agent was doing, and a service to
run it, all of which had to be kept in step with the SDK. What it added
that Claude could not do was small: the session lived on the matter and
the firm could see it. What it cost was a second surface to maintain and
a server that held the firm's files and ran an agent over them.

[Claude connects over a remote MCP server with OAuth](2026-10-30-claude-connects-over-remote-mcp.md)
had meanwhile given Claude's apps the same read of a matter that the
session's tools had, under each user's own Claude account. And the files
needed no server at all: Dropbox puts the Firm folder on every member's
computer, and a standalone watcher on the office server
([firm-index](https://github.com/Craig-Legal/firm-index)) keeps a text
index inside each matter folder, so Claude on any member's computer can
grep the matter's PDFs as plain text.

## Decision

The matter chat is retired. Kosmos has no AI tab: no sessions, no
archive of the earlier conversations, no sessions service, no Agent SDK.
The Files integration goes with it: the Dropbox daemon on the server,
the watcher, the matter-to-folder link, the status page and the text
index. `apps/drive` keeps only its migrations, as it already did for the
Google Drive mirror.

What stays is what something else needs. The `Conversation` and
`Message` rows stay, because intake chats and drafts are conversations,
with the few views their message templates call (status, cancel, delete,
citation vetting). The matter tools in `apps/ai/agent_tools.py`, the
context helpers and the service functions in `apps/ai/api.py` stay,
because the MCP server runs on them. The AI keys stay, because the
background features (summaries, the intake assistant, quick task entry)
and the intake chat run on them. Saved case law is its own Case Law tab
whenever CourtListener is set up.

Questions about a matter are asked in Claude, connected to Kosmos over
the MCP server and to the matter's files through Dropbox on the user's
own computer. The intake chat is decided separately.

## Consequences

- The `Session` and `SessionMessage` tables are dropped, with the
  sessions that were in them. The archived conversations stay in the
  database, unread by any screen, until the closed-matter purge removes
  them.
- The `SESSIONS_*`, `DROPBOX_*` and `FILES_*` settings are gone;
  `sessions.service` and `files-watcher.service` are removed from
  every server. The firm's files no longer touch the production server.
- Case law search by the AI, which the sessions offered through
  CourtListener, has no replacement in Kosmos: cases are added by
  citation, and research happens in Claude.
- The records that introduced sessions and the server-side files
  ([AI chat becomes Claude Code sessions](2026-10-29-ai-chat-becomes-claude-code-sessions.md),
  [Firm files live in Dropbox](2026-10-29-firm-files-live-in-dropbox.md))
  are superseded; the second still describes where the files live.
