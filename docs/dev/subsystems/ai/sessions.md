# Sessions

`apps/ai/sessions.py`, `runtime.py`, `session_tools.py`, `session_prompt.py`,
`management/commands/run_sessions.py`. A session is Claude Code run by
the Claude Agent SDK on one matter, from the matter's folder in the
firm's files. Record: [AI chat becomes Claude Code sessions
(2026-10-29)](../../../decisions/2026-10-29-ai-chat-becomes-claude-code-sessions.md).

## The shape of a turn

1. `session_send` records the prompt as a `SessionMessage` (role user)
   and creates the answer's row (role assistant, status `pending`). The
   first prompt names the session. The page's transcript partial now
   ends in a live block that polls `session_live` every second.
2. The sessions service (`manage.py run_sessions`,
   `deploy/systemd/sessions.service`) polls for pending answers and runs
   each on a pool thread, `SESSIONS_CONCURRENCY` at a time. A heartbeat
   in the `ai_status` cache (`runtime.service_alive`) lets the page say
   when the service is down instead of waiting.
3. `runtime.run_turn` builds the options and streams the harness:
   `cwd` is the linked matter folder (or a scratch directory of the
   session's own when none is linked, and the prompt says so); the
   built-in tools are Read, Grep and Glob only; the Kosmos tools come
   from the in-process MCP server; `permission_mode` is `dontAsk`, so
   anything not pre-allowed is refused; `setting_sources` is empty and
   `strict_mcp_config` is set, so nothing from the service account's
   own Claude Code configuration leaks in; `CLAUDE_CONFIG_DIR` is
   `SESSIONS_HOME`, where the harness keeps its transcripts; `resume`
   is the session's `sdk_session_id` from the previous turn. Caps:
   `SESSIONS_MAX_TURNS` and `SESSIONS_MAX_BUDGET_USD` per turn. The
   model and the effort are the session's (`Session.model`,
   `Session.effort`, set from the page's header badges; a session on an
   admin-only model that someone else continues falls back to the
   default at send). Thinking is adaptive with `display: "summarized"`,
   since the newer models send only a signature unless asked.
4. As messages arrive, `Turn` keeps the turn's events in order: the
   model's narration (`text`), its reasoning when the harness shows it
   (`thinking`, summarized, streamed as a draft while it is written,
   with how long it took), and each tool call (`tool`: a readable summary, what
   it asked for with the folder path stripped, and, once the result
   comes back, an outcome line, a 600-character preview, the error
   flag and the duration). With `include_partial_messages` the text
   being streamed rides along as a draft event ahead of its block, and
   the name of the call being prepared gives the activity line
   ("Read ...", "Writing", "Thinking"). The state flushes to the cache
   every half second; a cancel flag in the cache (`session_cancel`)
   interrupts the harness. The cache is a database table, so the
   writes hop to a thread from the event loop.
5. On the result the answer is saved: the final text (the harness's
   `result`, or the accumulated narration), the events as the trail
   (less the final text, which is the answer), tokens (uncached plus
   cache writes as input, cache reads apart), cost, duration, the
   status (`done`, `failed`, `cancelled`), and the session's
   `sdk_session_id`.

## The page

`templates/ai/sessions/`. `steps.html` renders the same event list
live and from a saved trail, Claude Code's transcript shape: a muted
call line with an elbow outcome line under it, opening to what was
asked and what came back; narration in full strength between the
calls; a thought collapsed to "Thought for 4s" and a one-line peek, as
in the desktop app. While a turn is open the live block shows the rows as they
happen under an activity line with a Stop button; once saved, the rows
fold into a "Worked for 8s · 3 steps" line above the answer.
`sessions.js` keeps a row the reader opened open across the polls and
follows the bottom only while the reader is already there. The model
and the effort are badge-styled dropdowns (`controls.html`, Alpine's
`dropdown()`) that post to `session_controls` and come back with the
new labels; the composer is the box alone, Enter sends.

## The tools

`session_tools.build_session_server` turns the specs of
`agent_tools.build_agent_tools` into MCP tools, running each call
through `make_agent_executor`'s `execute_one` on a worker thread, so
the earlier loop's handlers, permissions (financial, research) and
caps are reused unchanged. Added: `list_sessions` and `read_session`
for the new table; `search_files`, which searches inside the matter
folder's PDFs (their text layer), ODT and DOCX documents and plain text,
because the harness's Grep is ripgrep and reads bytes, so a PDF is
invisible to it (`apps/drive/text.py` through
`apps.case.services.search_folder_text`: text taken by `pdftotext` or
from the document's XML, cached outside the tree under
`FILES_TEXT_CACHE`, keyed by path and validated by size and mtime; the
watcher warms the cache for each PDF it checks and `manage.py
index_file_text` fills it for a tree); and `save_caselaw` for a user who
may research. Names reach the model as `mcp__kosmos__<name>`.

## The prompt

`session_prompt.build_session_system`: the legal prompt, a working
method (files by Glob, search_files and Read, Grep only on plain
text, Kosmos tools for the rest, cite what
you rely on, no writes), the research note when CourtListener is
available to the user, the source-linking rules, the matter overview,
contacts, witnesses and proceedings, and the top level of the matter
folder with item counts.

## Settings

| Setting | Meaning |
| --- | --- |
| `SESSIONS_HOME` | The harness's state directory for sessions (`CLAUDE_CONFIG_DIR`). Default `.claude-sessions/` under the application. |
| `SESSIONS_SCRATCH` | Working directory for a session whose matter has no linked folder. |
| `SESSIONS_CONCURRENCY` | Turns the service runs at once; each is a Claude Code process of up to about a gigabyte. |
| `SESSIONS_MAX_TURNS`, `SESSIONS_MAX_BUDGET_USD` | The harness's own caps per turn. |

The SDK ships its own Claude Code binary and uses it (the log says
"Using bundled Claude Code CLI"), so the host needs no separate
install. It needs an Anthropic API key (`ANTHROPIC_API_KEY` or
Settings) and the Dropbox-synced tree.

## What sessions replaced

The chat that preceded sessions (a context builder and selector, an
in-house tool loop over the same matter tools, fenced writes and
citation vetting after each answer) was retired on 2026-10-29
([record](../../../decisions/2026-10-29-the-conversation-engine-is-retired.md)).
Its conversations stay readable under the Archive pill; what remains
of its code is on [The archive and the intake chat](context.md).

## Tests

`apps/ai/tests/test_runtime.py` runs a turn against a scripted fake of
`ClaudeSDKClient` with an in-memory cache; `test_sessions.py` covers
the tab, the launch, the model gate, renaming and access.
