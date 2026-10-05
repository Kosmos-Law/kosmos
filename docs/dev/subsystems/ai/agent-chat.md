# Agentic chat

The case AI chat has two modes, chosen when a conversation is created
(`Conversation.kind`, fixed for its life like the model):

- **Classic** (`kind="classic"`): one completion over a preloaded matter
  context (`context.assemble_matter_context_with_selection()` and the
  Gemini Flash selector; see [AI chat and context](context.md)).
- **Agentic** (`kind="agent"`): a tool loop. The model gets a small,
  cache-stable orientation and read-only tools, decides which materials to
  open, and narrates as it goes. Modeled on how a coding agent works a
  repository: index first, read what matters, answer.

Both modes share the window, the 1s status poll, cancellation, message
creation, and the fenced-block writes (`tasks.finalize_response()`).
Intake and agenda chats stay classic. The agentic mode (2026-08-23) is the
successor of the retired research chat mode; see
[Research chat (retired)](../../../decisions/research-chat-retired.md).

## Where the code is

| Module | Holds |
|---|---|
| `apps/case/ai/agent.py` | `run_agent_request()`, the agent-mode twin of `tasks.process_ai_request()` |
| `apps/case/ai/agent_prompt.py` | The orientation: `build_agent_system()`, `build_agent_history()`, the material index, `RESEARCH_PROTOCOL` |
| `apps/case/ai/agent_working_set.py` | The carried-forward text of materials read in earlier turns |
| `apps/case/ai/agent_tools.py` | Tool definitions, `AgentBudget`, the executor and the parallel batch runner |
| `apps/case/ai/agent_state.py` | `AgentRunState` and `AgentStatusWriter`: the live payload and the persisted `Message.agent_run` |
| `apps/case/ai/agent_types.py` | `LoopResult`, `TurnUsage`, the forced-answer note |
| `apps/case/ai/anthropic_client.py`, `gemini_client.py` | `send_to_claude_with_tools()`, `send_to_gemini_with_tools()` |
| `apps/case/ai/caselaw_blocks.py` | The `save-caselaw` write block |
| `apps/case/ai/semantic.py`, `embeddings.py` | The pgvector index `search_materials` fuses with keyword hits |
| `templates/case/ai/agent-status.html`, `agent-step.html`, `agent-trail.html`, `chat-statusbar.html` | The live rows, the collapsed trail, the pinned bar |
| `apps/case/templatetags/ai_extras.py` | Filters for the trail and the bar |

## Flow

```
new-conversation modal (Mode: Classic | Agentic) -> ?kind=agent -> hidden form field
send_message (kind on create only) -> daemon thread -> tasks.process_ai_request
  -> kind == "agent": agent.run_agent_request
       system   = agent_prompt.build_agent_system     three segments, see below
       history  = agent_prompt.build_agent_history    answers only + earlier-reads note
       tools    = agent_tools.build_agent_tools
       executor = agent_tools.make_agent_executor     budget, dedupe, parallel batches
       loop     = anthropic_client.send_to_claude_with_tools
                | gemini_client.send_to_gemini_with_tools
       status   = agent_state.AgentStatusWriter -> ai_status_<id> (full state every write)
       finish   = tasks.finalize_response             draft edits, facts, witnesses,
                                                      notes, caselaw, handle links, citations
       payload  = complete {response, input_tokens, output_tokens, citations,
                            activity_log, agent_run}
views.ai_status -> status.html (+ agent-status.html) -> Message(agent_run=...)
messages.html / message-single.html -> agent-trail.html above the answer
```

Runs live on a daemon thread in the gunicorn worker like every chat turn,
so a deploy or a `.py` reload kills them mid-run (the heartbeat in
`status.py` reports it). Agent runs are minutes long; that caveat bites
harder here. Reloading the window mid-run re-attaches the poller
(`conversation_view()` checks the status key), so a run that finished
unwatched is still collected.

## Orientation (`agent_prompt.py`)

Segment A, byte-stable across turns while the matter is unchanged (so the
provider cache keeps hitting):

1. `apps/case/ai/prompts/legal.md` (the legal instructions, jurisdiction
   substituted)
2. the working method (orient from the index, read before relying, pinned
   first, batch independent reads, budget, one-sentence narration before
   each batch, answer rules), then, for a user with the Research
   permission, the legal research method (`RESEARCH_PROTOCOL`: factual
   predicate before searching, anchor mining via grep and citation lookup,
   a dedicated counter-authority pass, currency check, statutory text from
   at least two quoting opinions, published-authority preference, "could
   not verify" beats fabrication)
3. `SOURCE_LINKING` (the citing rules)
4. the matter overview, contacts, witnesses, proceedings
5. highlights and timeline inline when their combined text is under
   `INLINE_SECTIONS_MAX_CHARS` (40k), otherwise pointer lines to
   `read_matter_section`
6. the material index: every readable item as one line (handle, name,
   category, date, size, importance, pinned) grouped by kind. Over
   `INDEX_MAX_CHARS` (120k) it drops descriptions, then collapses the
   conversation and invoice groups to counts. Invoices are indexed only
   with the Financial permission.

The middle segment is the conversation's **working set**
(`agent_working_set.py`): the full text of materials read in earlier
turns, re-fetched from the database each turn and carried forward
verbatim under a `## Materials in View` header. Reads come from prior
`Message.agent_run` steps; each item is capped at 60k chars, the segment
at 200k (or what the history ceiling leaves after segment A), and
least-recently-read items are evicted first. Kept items render in
first-read order so the segment grows append-only, keeping the
prompt-cache prefix stable. Deleted or newly `never`-flagged items drop
out. Caselaw carries the opinion only while the 1h `read_caselaw` cache
still holds it, and CourtListener opinions only while the 24h
`agent_opinion_cluster_{id}` cache holds them (a prompt build never
fetches over the network).

Segment B, per turn: today's date and requester (`build_request_info()`),
any armed write protocols (`tasks.armed_write_protocols()`, with the
caselaw protocol only for a Research user), a linked draft.

`build_manifest(include_always=True)` feeds the index: "always" items are
listed too, flagged pinned; "never" items stay hidden. `ManifestItem`
carries `handle` (`doc:12`, `thread:<id>`, `note:5`, `lib:9`, `case:3`,
`conv:8`, `inv:4`), `pinned` and `size_chars` for it.

**Prior turns' tool calls are not replayed.** The history is the
conversation's user messages and answers; what earlier turns read is
carried instead by the working-set segment, and a system note on the
newest message lists only the reads NOT carried there (evicted or never
fetched), saying their text is not in the prompt. Bounded prompt, stable
cache prefix, no signed thinking blocks or `thought_signature`s to persist.

## Tools (`agent_tools.py`)

All read-only; results are JSON objects and every one carries
`budget: {calls_left, chars_left}`. Text reads take `offset` and
`max_chars` (default 60k, cap 150k) and report `total_chars`,
`next_offset`, `truncated`. The case-law tools (the last four rows) are
offered only to a user with the Research permission
(`access.has_research_access()`).

| tool | reads |
|---|---|
| `search_materials` | hybrid search over documents, highlights, facts, matter notes, library notes and emails (scoped to the matter, `never` excluded; emails grouped by thread): watson `websearch_to_tsquery` keyword pass fused with a pgvector semantic pass (`semantic_entries`) by reciprocal rank, trigram fuzzy fallback when nothing matches; document and library hits carry the AI `summary` when set; hits already returned this turn are flagged `seen`, and a mostly-seen repeat gets a note |
| `read_document` | `Document.ocr_text` when OCR finished, with `description` and AI `summary` when set; `never` refused |
| `read_email_thread` | the thread via `format_email_thread`, `gmail_id` fallback |
| `read_note` | a matter note or a library note (`get_library_notes`) |
| `read_caselaw` | saved case notes, summary and the opinion (`_fetch_caselaw_opinion_text`, cached 1h) |
| `read_conversation` | an earlier conversation's transcript |
| `read_invoice` | `format_invoice` (Financial permission) |
| `read_matter_section` | `apps.case.api.SECTIONS[section](matter)`, capped 150k; the money sections need the Financial permission |
| `search_caselaw` | CourtListener opinion search (`research.courtlistener.search_opinions` + `sanitize_query`), court filter from `get_court_ids` (state defaults from the matter's jurisdiction), optional `filed_after`; up to 3 query variants merged on cluster_id, `published` flag = has reporter citations |
| `lookup_citation` | `courtlistener.lookup_citation`: exact citation to case/cluster; not-found is a normal payload, not an error |
| `read_opinion` | full cluster text (majority + concurrences/dissents, capped 250k) via `_opinion_for_cluster`, cached 24h at `agent_opinion_cluster_{id}`; sliced like every read |
| `search_in_opinions` | literal case-insensitive grep across up to 10 cached/fetched opinions, up to 8 excerpt windows each with char offsets; per-id error isolation |

Budget per turn (`AgentBudget`): 40 calls, 600k chars read, 30 model
turns, 4 parallel workers. Calls are reserved before dispatch under a
lock; an exact repeat of a call (same name and input) is served from the
run cache, uncharged, with a note. Once the budget is gone the executor
answers budget errors; after two batches of nothing but budget errors,
or at the turn ceiling, the loop appends a forced-answer note and makes
one last turn with tools disabled.

One model turn's calls run together (`run_tool_batch`, order preserved;
pool workers close their DB connection). Each call emits one step, first
pending then finalized, so the live log shows one row per tool.

The `save-caselaw` fenced write (`caselaw_blocks.py`, agent conversations
only) is the authority ledger: when directed, the agent persists verified
cases to the matter's Saved case law with the cited proposition in
`notes`, deduped on the `(matter, cluster_id)` constraint (an existing row
gets the proposition appended), then the usual 200-word summary is queued
on qcluster.

## Provider loops

Same contract in both clients: `(system, messages, tools, execute_batch,
model, *, max_turns, is_cancelled, on_text, on_thinking, on_turn, on_note,
max_tokens) -> LoopResult`. Claude adds `effort` (the constant
`agent.AGENT_CLAUDE_EFFORT`, "high"). The assistant turn is echoed back
verbatim (thinking blocks included on Claude, the original `Part` objects
on Gemini for their `thought_signature`); the tool results go back as one
user message in block order. Claude runs adaptive thinking with the
summary requested where the model offers one
(`anthropic_client._thinking_for()`) and a rolling cache breakpoint on
the newest block; `TurnUsage.input` is
the whole prompt with `cache_read` broken out beside it so both providers
report alike. A `max_tokens` tool turn is retried once with a note;
Gemini's `MALFORMED_FUNCTION_CALL` likewise; a Claude `refusal` is terminal
(`stop_details` stored). Fable requests carry the server-side refusal
fallback (`anthropic_client.FALLBACK_MODELS`, Opus 5): a classifier
decline re-runs the turn on the fallback model inside the same call, the
run gets a note naming it, `LoopResult.served_model` records it, and the
echo drops the declined partial's thinking and tool_use blocks
(`_after_fallback()`). Only a whole-chain refusal is terminal. Fable keys
get `AGENT_FABLE_MAX_OUTPUT_TOKENS` (32k) because their always-on thinking
can spend a standard budget before reaching a tool call.

Requires `anthropic>=1.0` (the 0.40 stream accumulator dropped thinking
blocks, which the loop must echo back).

## Status payload and the persisted run (`agent_state.py`)

Every write carries the whole state:

```
status, message, started_at, mode="agent",
activity_log: [str] (last 60),
usage: {input, output, cache_read, cache_write, turns, tool_calls,
        tool_calls_max, chars_read, chars_read_max, per_turn: [...]},
steps: [...] (last 60)
```

Steps, in display order per model turn: `text` (the model's prose,
updated in place while streaming), `turn` (written when the turn ends,
with its tokens), one `tool` per call, and `note` when the loop
intervened. Statuses: `context`, `thinking`, `generating`, `reading`,
`searching`, `applying`, `verifying` (all have icons in `status.html`).

On completion `Message.agent_run` holds `{version, llm, model,
elapsed_seconds, stop_reason, stop_details, forced_answer, usage, budget,
steps}` (the full step list); `input_tokens`/`output_tokens` on the
message are the cumulative totals. An error payload carries the partial
run so a failed turn stays inspectable. `research_trail` is untouched:
it belongs to the retired research chat's renderer.

## UI

- `templates/case/ai/new-conversation-modal.html`: Mode (a Classic |
  Agentic select), Model, Name. New conversations default to Classic.
- `conversation-standalone.html`: hidden `kind` field, Agentic header
  badge; `table.html` shows the badge in the list.
- `status.html` includes `agent-status.html` for agent conversations: the
  typed rows (`agent-step.html`, stable ids for idiomorph) flow inline
  where the answer will land; the status line, elapsed time, token counts
  and cancel button live in the pinned bar above the composer
  (`chat-statusbar.html`), updated out-of-band by the same poll. The log
  pin yields to a reader who scrolled up.
- `agent-trail.html`: the same rows collapsed above the answer, totals
  in the summary. Filters in `apps/case/templatetags/ai_extras.py`.

## Access

Matter membership is checked centrally for `/case/<matter id>/...` routes
and by `access.conversation_for_user()` for the poll and cancel views, as
on the classic path. What differs is the toolset: `agent.run_agent_request()`,
`agent_prompt.build_agent_system()` and `agent_tools.build_agent_tools()`
each consult `has_financial_access()` and `has_research_access()` for the
requesting user, so invoices, the money sections and the case-law tools
exist only for a user who could open those screens. See the
[permissions reference](../../../reference/permissions.md).

## Things that bite

- **Segment A must stay byte-stable.** Anything per-turn (date, user,
  protocols, draft) belongs in segment B; a change to the order or text of
  segment A invalidates the provider cache for every open conversation.
- **The working set is append-only on purpose.** Items are admitted
  most-recently-read first until the cap and rendered in first-read
  order; re-sorting kept items would break the cache prefix.
- **Prompt builds never fetch.** An opinion whose cache has expired drops
  out of the working set silently; the earlier-reads note tells the model
  its text is gone.
- **The permission checks must agree.** `agent.py` gates the tool list,
  `agent_prompt.py` gates the research method and the `save-caselaw`
  protocol, both on `has_research_access()`; edit one and the prompt
  describes tools the model does not have, or the reverse.
- **`Message.agent_run["steps"]` is read by later turns.**
  `agent_working_set.reads_from_steps()` mines the `tool` steps of older
  messages for what was read; a change to the step shape must keep those
  readable.
- **Pool workers must close their DB connection** (`run_tool_batch`), or
  the thread pool leaks connections across runs.

## Tests

`apps/case/tests/test_agent_tools.py`, `test_agent_loop.py` (fake SDK
clients, no DB), `test_agent_prompt.py`, `test_agent_run.py` (fake loop,
real tools), `test_agent_working_set.py`, `test_agent_research_access.py`,
`test_caselaw_blocks.py`, `test_ai_extras.py`, plus the agent cases in
`test_views_ai.py` and `test_research_history.py`.

## Related

- [AI chat and context](context.md) for everything the modes share.
- [AI chat](../../../guide/ai-chat.md) in the user guide shows the window.
- [Research tab](research-tab.md) for the CourtListener client and
  jurisdictions the research tools reuse.
