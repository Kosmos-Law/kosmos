# AI is optional (2026-10-06)

Until this change Kosmos assumed AI. The matter **AI** tab, the intake
Assessment and Chat, the AI context controls and the background
summaries were always there, and most of the background work was
hard-wired to Gemini. A server with no keys still showed every AI
surface; a chat answered "Error: Unable to get response.", the summary
tasks failed into the log, and forwarded intake email was recorded as
failed. Keys could be set only in `config/.env`, so a firm whose
administrator does not edit server files could not turn AI on at all.

The owner wants AI to be optional and invisible unless it is set up. A
new firm may not want AI at all (for confidentiality, cost, or simply
preference), and it should then get a complete practice-management
application with no dead AI buttons, no errors, and nothing sent to a
provider.

## Decision

AI is on when at least one provider has a key, and off otherwise.

- **Where keys come from.** `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` in
  `config/.env`, or a key an administrator enters under Settings >
  Integrations. A `.env` key wins and shows "Set in config/.env". A
  Settings key is checked against the provider (by listing its models)
  before it is saved, stored on `Firm` encrypted with a key derived from
  `SECRET_KEY`, excluded from the Django admin, and can be removed.
  `apps/settings/ai.py` holds the rule (`configured_providers()`,
  `ai_enabled()`).
- **Without a key, AI is absent, not broken.** The matter AI tab, the
  drafts companion, intake Assessment and Chat, the AI column, bulk menu
  and form field on Documents and Case Law, and Settings > Tasks are
  hidden (the `integrations` context processor), and the AI and drafts
  routes answer 404 for everyone (`AI_PATTERN` in
  `PermissionMiddleware`). No AI work is queued: summaries and semantic
  indexing skip, and forwarded intake email builds the intake from the
  raw message without counting it a failure. AI quick-add needs both
  the firm toggle and a key.
- **Either provider runs everything.** Every AI feature other than the
  matter chat goes through `apps/case/ai/providers.py`'s `complete()`
  with a tier (`fast` or `deep`) rather than a model, and runs on
  whichever provider is configured, Gemini first when both are. Intake
  chats record their provider and stay on it. The matter chat's picker
  offers only the configured providers' models. The one exception is
  semantic search, whose embeddings are Gemini's: without a Gemini key
  search is keyword-only, without any notice.
- **Saved case law follows CourtListener, not AI.** With a
  CourtListener token and the Research permission, it is the AI tab's
  Case Law view when AI is on and its own Case Law tab when AI is off.
  Without a token it is hidden and its routes 404.

## Alternatives considered

- **Keys in `config/.env` only.** Simpler, and secrets would stay in one
  place. Rejected because turning AI on, or off, is a firm decision that
  the person running the firm's Kosmos should be able to make without a
  shell and a restart. `.env` still works and takes precedence, for
  operators who manage secrets there. The cost is that rotating
  `SECRET_KEY` (or restoring a database onto a server with another one)
  loses the stored keys, which must then be re-entered.
- **Each feature follows its own provider.** Keep the Gemini-only
  features Gemini-only and show each one when its provider is set. This
  would have left a firm with only an Anthropic key with chat and almost
  nothing else, and made the question "is AI on?" a per-feature matrix
  for users and for the code. Routing through tiers made one switch
  possible.
- **Gemini required, Anthropic optional.** The background work was
  already Gemini's, so requiring it was the smallest change. Rejected
  because it forces a firm that has chosen Anthropic to open a second
  provider account and send client material to it. Only embeddings stay
  Gemini-only, because Anthropic offers no embedding model, and they
  degrade quietly to keyword search.
- **Hide the links but keep the routes.** Rejected for the same reason
  as every other gate in Kosmos: hiding a link is not a gate. A bookmark
  or an old link must not open a feature the server does not have.

## Consequences

- A fresh install with no keys shows no AI and sends nothing to any AI
  provider. Turning AI on later does not backfill summaries for material
  added meanwhile; library notes have `backfill_note_summaries`, and
  semantic search has `build_semantic_index`.
- A new AI feature must check `ai_enabled()` (or hide behind the context
  variable and, for a route, sit under `AI_PATTERN`), and call
  `providers.complete()` with a tier rather than a provider client.
  Calling `send_to_gemini()` directly would bring back a Gemini-only
  feature.
- Tests run with fake keys for both providers and CourtListener by
  default (`_integration_keys` in the root `conftest.py`), so no test
  can spend; `ai_off` and `courtlistener_off` cover the unset case.
- Migration `apps/settings/migrations/0010_firm_ai_keys.py` adds the two
  encrypted key fields to `Firm`.

## Evidence

- Commit `10f4fd610`, "feat: AI is optional, on when a provider key is
  set" (2026-10-06).
- `apps/settings/ai.py`, `apps/case/ai/providers.py`,
  `config/context.py`, and `AI_PATTERN` and `CASELAW_PATTERN` in
  `apps/accounts/middleware.py`.
- `apps/case/tests/test_ai_optional.py` and
  `apps/settings/tests/test_ai_keys.py`.

## Related

- [AI providers and research](../admin/integrations/ai.md): setup,
  precedence, and what a server without a key shows.
- [AI chat and context](../dev/subsystems/ai/context.md#ai-is-optional):
  how the gates are built.
- [The Research tab is retired](2026-10-06-research-tab-retired.md):
  where saved case law moved before this change.
- [Scheduled AI jobs run only when ENV is prod](2026-07-30-scheduled-ai-jobs-run-only-in-production.md).
