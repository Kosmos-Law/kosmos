# The archive and the intake chat

What is left of the retired matter chat: the `Conversation` and
`Message` rows (kept, since intake chats and drafts are conversations),
the intake chat that still runs on them, and the helpers and matter
tools the [MCP server](../mcp.md)'s service functions share. The engine
itself (the context builder and selector, the in-house tool loop, the
fenced writes and citation vetting after each answer) was retired on
2026-10-29
([record](../../../decisions/2026-10-29-the-conversation-engine-is-retired.md)),
and the chat's screens, with the Claude Code sessions that briefly
replaced them, on 2026-10-30
([record](../../../decisions/2026-10-30-ai-chat-retired.md)): questions
about a matter are asked in Claude's own apps over the MCP server. All of
it is optional: with no provider key configured, none of it is reachable
(see [AI is optional](#ai-is-optional)).

## Where the code is

| Module | Holds |
|---|---|
| `apps/ai/models.py` | `Conversation`, `Message` |
| `apps/ai/views.py` | `ai_status` / `cancel_request`, the status poll the intake chat uses; `delete_message`; the citation vetting modal and status the shared message templates call |
| `apps/ai/context.py` | The shared helpers: `build_request_info()`, `build_chat_history()`, `load_legal_prompt()`, `SOURCE_LINKING`, and the section formatters (`format_matter_overview()`, `format_contacts()`, …) the matter tools and the MCP API read |
| `apps/ai/agent_tools.py` | The read-only matter tools (search, documents, email, the matter record, case law); `search_materials()` in `api.py` runs the MCP server's search through them |
| `apps/ai/prompts/legal.md` | The legal system prompt |
| `apps/llm/status.py` | The cross-process status store and heartbeat (the intake chat's turn) |
| `apps/ai/access.py` | Who may use a conversation and the Financial and Research gates |
| `apps/llm/anthropic_client.py`, `gemini_client.py` | `send_to_claude()`, `send_to_gemini_streaming()`: one completion with streaming and prompt caching |
| `apps/llm/providers.py` | `complete()`, the one call for background AI work; the `fast` and `deep` tiers and their model ids; `provider()`, `chat_llm()`, `AINotConfigured` |
| `apps/settings/ai.py` | Whether AI is set up: `configured_providers()`, `ai_enabled()`, `gemini_key()`, `anthropic_key()`, `key_source()`, and the encryption of keys stored on `Firm` |
| `config/context.py` | The `integrations` context processor: `ai_enabled`, `caselaw_available` and the firm's `case_file_enabled` and `accounting_enabled` for templates |
| `apps/ai/fact_blocks.py`, `witness_blocks.py` | The fenced write blocks' parsers, now reached by the MCP API's create routes |
| `apps/ai/vetting.py` | `has_pending_vetting()`, the reader of stored vetting results |
| `apps/ai/purge.py` | The closed-matter chat purge |
| `apps/case/semantic.py`, `apps/llm/embeddings.py` | The pgvector index behind `search_materials` |
| `apps/llm/pricing.py` | Estimated cost per message |
| `templates/ai/` | `messages.html` and `message-single.html` (the intake chat's window), `status.html` (its poller), the trail and citation partials, and `draft-chip.html` and `companion-setup.html`, which the drafts views render |
| `apps/intakes/chat.py` | The intake chat, built on the same models and status protocol |

## Data model

A `Conversation` belongs to exactly one of a `matter` or an `intake`
(both `CASCADE`); the code, not the database, keeps that exclusive.
`user` is who started it (`SET_NULL`). `llm` and `kind` (`classic`,
`agent`, or the older `research`) say how it was run. `ai_context`
(`auto`, `always`, `never`) still decides whether the MCP server's
conversations section lists it (`apps/ai/api.py`), and `summary` is the précis the
engine wrote after each answer.

A `Message` has a `role`, `content`, the sending `user` for user
messages, token counts, and the JSON fields the renderers read:
`verified_citations`, `activity_log`, `agent_run` (the old agentic
turns' trails) and `research_trail`. Both models keep
`HistoricalRecords`. Nothing writes a matter conversation now; the
intake chat writes its own.

## The intake chat's turn

`apps/intakes/chat.py` runs a turn on a thread: it seeds the run's entry
in the status cache, calls `providers.complete()` with the intake's
prompt, and writes the finished answer into the entry. The window polls
`ai_status` (`ai/status.html`, every second with an idiomorph swap);
when the entry says complete or error, the view writes the answer as a
`Message` and answers with `message-single.html` under a different
root, which ends the poll. A missing entry while a reply is outstanding
means the thread died with its process, and the view writes an
"interrupted" note instead of polling forever. `cancel_request` marks
the entry cancelled and deletes the pending question.

### AI is optional

`apps.settings.ai.ai_enabled()` is true when `configured_providers()` is
non-empty. A provider is configured when its key is in `config/.env` or
stored on the `Firm` row (`gemini_api_key`, `anthropic_api_key`). Stored
keys are Fernet tokens under a key derived from `SECRET_KEY`
(`_fernet()`), so a new `SECRET_KEY` makes `decrypt_key()` return ""
with a logged warning, and the provider counts as unconfigured. The
admin-only form is `ai_key_save` in `apps/settings/integrations/views.py`
(`templates/settings/integrations/ai.html`): `verify_ai_key()` lists the
provider's models with the candidate key before saving it, and an empty
value removes it. There is no cache: each check reads the
`Firm` row (at most once per call), so a saved key takes effect in every
process at once.

Four layers keep a server without a key free of AI:

- **Templates.** The `config.context.integrations` context processor puts
  lazy `ai_enabled` and `caselaw_available` in every template context
  (evaluated only when a template reads them). They hide the AI tab and
  its Case Law switch (`case-nav.html`, `ai/view-pills.html`), the
  intake Assessment pill and its Assess and Chat buttons, the AI column
  and bulk menu on Documents and Case Law, and the Settings > Tasks menu
  entry.
- **Routes.** `PermissionMiddleware.__call__` matches `AI_PATTERN`
  (`/case/…/ai/`, `/case/drafts/`, `/intakes/<id>/assess`,
  `/intakes/<id>/chat/` and `/settings/tasks/`) and answers 404 for everyone, admins included,
  when `ai_enabled()` is false. `CASELAW_PATTERN` does the same for saved
  case law and the cluster viewer when there is no CourtListener token.
  Both run before the permission checks.
- **The remembered tab.** `tab_available(user, tab)` in
  `apps/case/views.py` says whether `ai` or `caselaws` can be shown;
  `get_last_tab()` falls back to Documents for a stored tab that no
  longer is.
- **Background work.** Every summary task, its queueing helper, the
  semantic enqueue and the inbound intake pipeline check `ai_enabled()`
  (or `gemini_key()`) first and return. `FilesForm` drops `ai_context`,
  leaving the stored value alone. `quick_add_ai_enabled()` requires both
  `Firm.quick_task_ai` and `ai_enabled()`.

Saved case law follows CourtListener rather than AI:
`courtlistener.caselaw_available(user)` is a token plus admin or
`perm_research`. With AI on, the list is a view of the AI tab; with AI
off, `case-nav.html` shows it as its own Case Law tab.

Tests: the root `conftest.py` gives every test fake Gemini, Anthropic and
CourtListener keys (autouse `_integration_keys`), the same on a laptop
with real keys in `config/.env` as in CI, so a stray real call fails
instead of spending. Request the `ai_off` or `courtlistener_off` fixture
to test the unset case; `apps/case/tests/test_ai_optional.py` and
`apps/settings/tests/test_ai_keys.py` are the examples.

## Access

Routes under `/case/<matter id>/...` are checked for matter membership by
`PermissionMiddleware.process_view()` in `apps/accounts/middleware.py`.
The status, cancel and intake routes name no matter, so `access.py`
fills the gap: `conversation_for_user()` (a matter chat needs the
matter, an intake chat the Intakes permission) guards the poll and
cancel views.

`has_financial_access()` (admin or `perm_financial`) decides whether the
matter tools offer invoices, and `has_research_access()` (admin or
`perm_research`) whether they offer case law. The matrix is in the
[permissions reference](../../../reference/permissions.md).

## Things that bite

- **The intake chat tests monkeypatch `threading.Thread`** to
  run the worker inline; `status.py` binds `Thread` at import so the
  heartbeat stays a real thread, or that patch turns its wait loop into a
  hang.
- **`message-single.html` and `messages.html` are the intake chat's**,
  and the drafts views render `draft-chip.html` and
  `companion-setup.html` from the same folder: `templates/ai/` is not
  dead because the matter chat is.

## Related

- [MCP server and JSON APIs](../mcp.md), where questions about a matter
  are answered now.
- [AI providers and research](../../../admin/integrations/ai.md) covers
  keys, the prompt file and retention for operators;
  [Background worker](../../../admin/worker.md) covers qcluster.
- Neighbouring pages: [MCP server and JSON APIs](../mcp.md),
  [Email and intakes](../email-and-intakes.md).
