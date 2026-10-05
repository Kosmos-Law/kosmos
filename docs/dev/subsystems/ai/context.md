# AI chat and context

The AI machinery under `apps/case/ai/` turns a matter's record into a
system prompt, runs a model call on a background thread, reports progress
to a polling view, and applies the writes the model was directed to make.
Four surfaces share it: the case chat (the matter's **AI** tab), the
intake chat (`apps/intakes/chat.py`), the Dash agenda chat
(`apps/dash/agenda.py`) and the nightly auto-summary threads. Agentic-mode
internals are on [Agentic chat](agent-chat.md); the Research tab's
pipeline is on [Research tab](research-tab.md).

## Where the code is

| Module | Holds |
|---|---|
| `apps/case/ai/models.py` | `Conversation`, `Message`, `MaterialChunk` |
| `apps/case/ai/views.py` | The case chat views: list, send, status poll, cancel, Compose Prompt, context preview |
| `apps/case/ai/tasks.py` | `process_ai_request()` (the classic turn), `finalize_response()`, `armed_write_protocols()`, the model dispatch tables, the window-fit guard |
| `apps/case/ai/context.py` | The context builders: section formatters, `collect_context_items()`, `assemble_matter_context_with_selection()`, `build_request_info()`, `build_chat_history()` |
| `apps/case/ai/selector.py` | The Gemini Flash selector: `build_manifest()`, `select_context()`, token estimates and model limits |
| `apps/case/ai/prompts/legal.md` | The legal system prompt |
| `apps/case/ai/status.py`, `access.py` | The cross-process status store and heartbeat; who may use a conversation and the Financial and Research gates |
| `apps/case/ai/anthropic_client.py`, `gemini_client.py` | Provider calls, streaming, prompt caching, the tool loops |
| `apps/case/ai/fact_blocks.py`, `witness_blocks.py`, `note_blocks.py`, `caselaw_blocks.py` | The fenced write blocks |
| `apps/case/ai/handles.py`, `citations.py`, `vetting.py` | Leaked `[doc:ID]`-style handles become links or note chips; citation extraction and CourtListener verification; the Flash vetting job |
| `apps/case/ai/auto_summary.py`, `purge.py` | The nightly threads; the closed-matter chat purge |
| `apps/case/ai/semantic.py`, `embeddings.py`, `pricing.py` | The pgvector index behind the agent's `search_materials`; estimated cost for the status bar |
| `templates/case/ai/` | The chat window, `status.html` (the poller), `prompt-editor-modal.html`, message partials |
| `apps/dash/agenda.py`, `apps/intakes/chat.py` | The agenda and intake chats, built on the same models and status protocol |

## Data model

A `Conversation` belongs to exactly one of a `matter`, an `intake` or an
`agenda_user` (all three `CASCADE`); the code, not the database, keeps
that exclusive. `user` is who started it (`SET_NULL`); the nightly
threads leave it null, which is how
`auto_summary._get_or_create_conversation()` tells a system thread from a
human one with the same title. `llm` and `kind` (`classic`, `agent`, or
the retired `research`) are fixed when the conversation is created.
`ai_context` (`auto`, `always`, `never`) says whether this conversation is
offered to other conversations on the matter as a reference, and `summary`
is the Flash-written précis the selector reads. `vet_citations` turns the
post-answer vetting job on.

A `Message` has a `role`, `content`, the sending `user` for user messages,
token counts, and JSON fields the renderers read: `verified_citations`,
`activity_log` (the live log preserved on the answer), `agent_run` (agent
turns) and `research_trail` (old research-kind answers). Both models keep
`HistoricalRecords`.

`MaterialChunk` is one embedded chunk of a document, note, library note,
email, highlight or fact, unique on `(kind, object_id, chunk_index)`, with
an HNSW index on its vector; `semantic.py` writes it on save through
qcluster and `manage.py build_semantic_index` backfills.

## How a turn runs

1. **Send.** `views.send_message()` creates the conversation on the first
   message (title, `llm`, `kind` from the form), stores the user
   `Message`, seeds `ai_status_<conversation id>` with `starting`, and
   starts a daemon `threading.Thread` on `tasks.process_ai_request()`.
   The response is `messages.html` with the poller in it. The agenda and
   intake chats have their own send views and workers
   (`_process_agenda_chat()`, `_process_intake_chat()`) on the same protocol.
2. **Context.** For a classic matter chat the thread calls
   `context.assemble_matter_context_with_selection()` (below), appends a
   linked draft's section when the conversation has one, then
   `SOURCE_LINKING` (the citing conventions) and whatever write protocols
   `armed_write_protocols()` returns. An agent conversation branches here
   to `agent.run_agent_request()` instead.
3. **History and fit.** `build_chat_history()` prefixes every message
   with its sent time and, when more than one person has taken part, the
   sender's name. `fit_prompt_to_window()` drops the oldest messages until
   the estimate fits 80% of the model window; for a Claude model whose
   estimate is past half the window it asks the API for an exact count and
   trims again against 98%. A context that cannot fit on its own raises
   `PromptTooLargeError`, which becomes the chat's error message.
4. **Model call.** `GEMINI_MODELS` keys go to
   `gemini_client.send_to_gemini_streaming()` with thought summaries
   feeding the status line; everything else goes to
   `anthropic_client.send_to_claude()`. Fable keys get a higher output
   ceiling because their thinking cannot be turned off.
5. **Finalize.** `finalize_response()` applies draft edits, the fenced
   write blocks, leaked-handle links, and the CourtListener citation check,
   in that order. It is the one path both modes write through.
6. **Complete.** The thread writes a `complete` payload (response, tokens,
   citations, log) under the status key with `FINAL_TTL`, and the next
   poll stores the assistant `Message`, starts the summary and vetting
   threads, and deletes the key.

**Compose Prompt** (`views.prompt_editor_modal()`,
`templates/case/ai/prompt-editor-modal.html`) is a rich-text editor whose
markdown is posted to the same `ai-send` route; its hidden `kind` field
carries the mode the window was opened in, because the first message
creates the conversation. The draft lives in `localStorage` per conversation.

### What goes into the context

`assemble_matter_context_with_selection()` builds the system prompt in
this order: `build_request_info()` (today's date, the requesting user,
the firm roster with titles, so the model never guesses a colleague's
role), the legal prompt, then `MATTER_CONTEXT_TEMPLATE`: overview,
contacts, witnesses, proceedings, the always-included items by importance
tier, tasks, events, time entries and settlement. After the template come
the selector's **Selected Materials** and an **Also Available** listing of
what it left out, so the model can name an item and ask for it.

`collect_context_items()` gathers the always-included items: documents,
saved cases and email threads with `ai_context="always"`, every highlight
and fact, and other conversations on the matter set to **Always**. Notes
have had no AI setting since 2026-08-11 and are all selector material.
Items set to **Never** are excluded everywhere.

`format_time_entries(matter, include_billing=...)` lists the work done;
with `include_billing` each entry also carries its rate, fee, comp flag
and invoice status. Since 2026-10-02 every requesting user gets that
detail (the Activity screens show it to anyone who can see the matter).
Invoices are different: `build_manifest(include_invoices=...)` offers them
to the selector only when `access.has_financial_access(user)` is true. A
run with no user (the nightly auto-summary, which every member of the
matter reads) sees neither money on time entries nor any invoice.

Library notes (standalone notes in folders flagged as AI library,
`apps.notes.models.get_library_notes()`) are offered on every matter when
`include_library` is true; the selector prompt tells the model to pick at
most five and only when the topic bears on the question.

**Reuse.** The assembled context is cached under `ai_ctx_<conversation id>`
in the cross-process `ai_status` cache (zlib-compressed, since it is the
whole system prompt) for `CONTEXT_REUSE_SECONDS` (600) together with a
fingerprint from `_context_fingerprint()`: count and latest `updated_at`
per source table, the model, the user and their Financial flag. A follow-up inside ten
minutes with an unchanged fingerprint skips the selector entirely, which
also keeps the provider prompt caches warm. Any write to the material,
including the AI's own note, fact or witness writes, changes the
fingerprint. Tasks, events and time entries are deliberately not
fingerprinted.

**Ceilings.** The selector works to `MODEL_CONTEXT_LIMITS` (about 60% of
each window) less the fixed sections and a 10k reserve. If the whole
prompt still estimates past 80% of `MODEL_HARD_LIMITS`, the selected
items are demoted to the Also Available list; if the always-included
content alone is still over, tiers are shed reference first, then
medium, then high (critical items are never dropped) and listed under
**Omitted Materials**. `estimate_tokens()` uses 2.5 characters per token:
the folk figure of 4 let a prompt through that the provider rejected.

### The selector

`selector.build_manifest()` lists every candidate as a `ManifestItem`
(type, id, name, category, date, a description, word count, importance)
with a `content_map` of the full text, resolved lazily for invoices and
case law (the opinion is fetched from CourtListener on selection). The
manifest covers `auto` documents with finished OCR, all matter notes,
`auto` saved cases, other `auto` conversations (described by their
`summary`), `auto` email threads as one item per thread, invoices when
permitted, and library notes. With `include_always=True` (the agent's
index) the `always` items are listed too, flagged `pinned`, each with the
`handle` the agent tools read by.

`select_context()` skips the model call when the matter items total under
`SMALL_MATTER_THRESHOLD` (30,000 words) and there are no invoices or
library items: everything goes in. Otherwise `SELECTOR_SYSTEM_PROMPT` and
the formatted manifest go to `gemini-2.5-flash`, which returns a JSON list
of `{type, id}`; if the call or the parse fails, `_fallback_by_importance()`
fills the budget by importance. Invoices and library notes never ride the
short-circuit or the fallback: they enter only when the selector names them.

### The system prompt file

`apps/case/ai/prompts/legal.md` is read fresh on every call by
`context.load_legal_prompt()` (an edit takes effect without a restart)
and its `[JURISDICTION]` placeholders are replaced with the matter's
jurisdiction, else the firm's, else "United States common law". The same
text heads the agent's orientation and the auto-summary context. The
operator page
[AI providers and research](../../../admin/integrations/ai.md) describes
what to edit in it.

### Providers

The picker keys in `Conversation.LLM_CHOICES` map to provider model ids
in `tasks.CLAUDE_MODELS` and `tasks.GEMINI_MODELS`; retired keys stay in
the tables so old conversations still send, and
`views.available_llm_choices()` hides a provider's models when its key is
not configured. Keys come from `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`
in `config/settings.py` (see the
[environment reference](../../../reference/environment.md)). Every model in
both tables has a one-million-token window. Each client marks the system
prompt cacheable (Anthropic's `cache_control`; a Gemini `cachedContents`
object held ten minutes for prompts over 130k characters) and streams so
a cancel stops the bill. Fable keys carry Anthropic's server-side refusal
fallback to Opus 5 (`anthropic_client.FALLBACK_MODELS`). Gemini Flash is
hard-wired for the selector, conversation summaries and citation vetting,
Gemini Pro for the intake, agenda and auto-summary threads.

### Status and the poller

`status.py` holds the run status under `ai_status_<conversation id>` in
the `ai_status` cache, a `DatabaseCache` on the `ai_status_cache` table
(`config/settings.py`; `manage.py createcachetable` creates it, not a
migration). It replaced the per-process `LocMemCache` on 2026-08-17:
production runs several gunicorn workers, a poll usually lands in a
different worker from the run thread, and each worker's private view made
most first polls find nothing and fabricate "server restarted" replies.

Liveness is TTL-based. In-flight writes carry `RUNNING_TTL` (180 s) and a
`RunHeartbeat` thread re-touches the entry every `HEARTBEAT_SECONDS`
(30). Terminal payloads carry `FINAL_TTL` (600 s) so a poller that arrives
late can still collect them. `views.ai_status()` is shared by the three
chats: a missing key while the latest message is still the user's means
the process died, and the view writes the "interrupted" assistant message
itself; `complete` and `error` are stored as messages; `cancelled` is left
in place so the thread's `is_cancelled()` keeps seeing it.

`templates/case/ai/status.html` polls every second with `hx-swap="morph"`
(idiomorph) so the box is patched, not replaced; a page that hosts it
must load idiomorph. The interval ends when a terminal reply swaps in a
different root element, and `views._terminal()` adds `HX-Reswap: outerHTML`
so that swap also works without idiomorph: before it, the intake window's
poller ran on forever and wrote an "interrupted" message every second
(2026-08-23).

### Fenced write blocks

The model writes to the record only through fenced blocks in its reply:
`create-facts` and `create-witnesses` (lists), `create-note` and
`edit-note` (one object each), `save-caselaw` (agent conversations only),
and the agenda chat's `create-tasks` (`apps/dash/agenda.py`, through
`apps.tasks.services.create_task_from_ai_entry()`). The intake chat has
its own `update-intake` block. A protocol is added to the system prompt
only when the last few user messages (the current one and the three
before it) match its trigger pattern (`FACTS_TRIGGER_RE` and the like),
so an ordinary chat carries no standing write instructions to misfire
on, and a follow-up ("also add the crash date") keeps the protocol armed.

`finalize_response()` applies each block with a regex substitution over
the reply (`apply_fact_blocks()`, `apply_witness_blocks()`,
`apply_caselaw_blocks()`, `apply_note_blocks()`), replacing the block with
confirmation lines so the user and the model's later turns both see what
happened. Nothing is confirmed first: the row exists by the time the
answer renders. A block that is not valid JSON is left as text and writes
nothing. Entry creators are forgiving on optional fields and strict on
the row itself (a fact's description, a witness's name); cited document
and highlight ids are filtered to the matter, so a guessed id links
nothing; a same-named witness is reused; a case already saved gets the
proposition appended to its notes rather than a duplicate row
(`(matter, cluster_id)` is unique). Each creator is also what the MCP
server's write tools call (see [MCP](../mcp.md)).

Note writes apply on the chat's worker thread, synchronously, and are
never refused: the per-note `Note.ai_write_until` grant gates only the
MCP server's `write_note`, not the in-app AI. Creation is limited to the
matter's notes; edits reach the matter's notes and library notes, and
every edit lands in the note's history under the requesting user, so a
bad one is recoverable. Because a model that has seen real confirmations
sometimes imitates the line instead of emitting the block,
`strip_fake_note_confirmations()` runs on the raw reply before the blocks
are applied and turns a lookalike into an honest "no note was changed"
notice.

## Background work

Chat turns are not qcluster jobs: they run on daemon threads inside the
web worker, so a deploy or a `.py` reload kills them, the heartbeat
stops, the key expires and the next poll reports the interruption. So do
the conversation summary (`tasks.generate_conversation_summary()`) and
the vetting job, started from the status view.

The auto threads do run on qcluster. `refresh_auto_summaries()` queues
`refresh_matter_auto_summary()` per open matter, which rewrites the
"Auto Summary" conversation with Gemini Pro and then queues
`refresh_matter_auto_agenda()` so the agenda sees the fresh summary. Each
thread is one prompt and one reply, `ai_context="always"`; attorney
discussion in the thread during the day is folded into the next refresh as
guidance, then the thread resets. A later run is incremental
(`build_incremental_context()`: the previous reply plus records changed
since it, with a ten-minute margin) unless the delta exceeds 300k
characters or the prompt text has changed, in which case it rebuilds
through the full selection pipeline with no user and no library. A failed
call keeps the previous version. The schedule targets run only when `ENV`
is `prod`, because a development database restored from production
inherits the schedule rows; `run_auto_summaries` bypasses that guard. The
schedules are installed by `setup_schedules`; see the
[schedules reference](../../../reference/schedules.md).

`purge.purge_closed_chats()` deletes every matter conversation, its
messages and their history rows once the matter's current Closed streak
(read from the matter's history) is older than `CHAT_RETENTION_DAYS`
(180; 0 keeps chats), from the weekly `chat-purge-weekly` schedule or the
`purge_closed_chats` command. Intake and agenda chats are not in scope:
they are deleted when ended or discarded.

## Access

Routes under `/case/<matter id>/...` are checked for matter membership by
`PermissionMiddleware.process_view()` in `apps/accounts/middleware.py`.
That check never sees a conversation id in the query string or the body,
and the status, cancel, intake and agenda routes name no matter, so
`access.py` fills the gaps: `conversation_for_user()` (a matter chat needs
the matter, an intake chat the Intakes permission, an agenda chat is its
owner's) guards the poll and cancel views, and
`matter_conversation_for_user()` ties a posted conversation id to the
matter in the URL with a 404, so a wrong id confirms nothing.

The reply is built for the user who asks (tightened 2026-10-02):
`has_financial_access()` (admin or `perm_financial`) decides whether
invoices are offered, and `has_research_access()` (admin or
`perm_research`) whether the agent gets the case-law tools and the save
protocol. The matrix is in the
[permissions reference](../../../reference/permissions.md).

## Things that bite

- **Never edit a `.py` while a run may be in flight.** The worker reloads,
  the daemon thread dies with it, and the user gets the "interrupted"
  reply. Agent runs are minutes long.
- **Order inside `finalize_response()` is fixed.** Draft edits first;
  `strip_fake_note_confirmations()` before `apply_note_blocks()` (after,
  a real confirmation would match); handles after the blocks that consume
  them; citations last.
- **The model tables must stay in step.** A new picker key needs
  `LLM_CHOICES` (and a migration for the choices), `CLAUDE_MODELS` or
  `GEMINI_MODELS`, `MODEL_CONTEXT_LIMITS`, `MODEL_HARD_LIMITS` and the
  `pricing.py` rates. Anthropic publishes no "latest" alias, so each
  version is a new key.
- **The agenda and intake chat tests monkeypatch `threading.Thread`** to
  run the worker inline; `status.py` binds `Thread` at import so the
  heartbeat stays a real thread, or that patch turns its wait loop into a
  hang.

## Related

- [AI chat](../../../guide/ai-chat.md) in the user guide shows the screens.
- [AI providers and research](../../../admin/integrations/ai.md) covers
  keys, the prompt file, scheduled jobs and retention for operators;
  [Background worker](../../../admin/worker.md) covers qcluster.
- Neighbouring pages: [Agentic chat](agent-chat.md),
  [Research tab](research-tab.md), [MCP server and JSON APIs](../mcp.md),
  [Case building](../case-building.md),
  [Notes and drafts](../notes-and-drafts.md),
  [Email and intakes](../email-and-intakes.md).
