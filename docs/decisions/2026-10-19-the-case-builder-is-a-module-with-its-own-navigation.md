# The case builder is a module with its own navigation (2026-10-19)

Kosmos is two products in one codebase. The practice manager manages
data: matters, contacts, calendar, tasks, time, invoicing, trust,
intakes. The case builder manages content: the matter's documents and
their OCR text, highlights, the timeline of facts, witnesses, labels,
saved case law, the notes and the firm library, search inside the
matter, and the Drive mirror that feeds the documents. The owner uses the
case builder less than the practice manager, expects it may retire one
day, and has always felt it deserved a top-level navigation of its own
rather than a pill pair inside a matter record.

Until this record the case builder was `apps/case` with the AI chat
engine inside it, reached through the Case pill in the matter header,
and everything imported everything: the AI module read ledger, trust,
time entries and tasks and was imported by intakes, tasks, notes, mail
and drafts; the accounts, matters and settings apps reached into the
case app; the case app's URL module mounted the mail and drafts views.

## Decision

The case builder becomes a module inside the one application, with a
known surface, and gets its own place in the sidebar. It is not split
into a second service.

- **The AI engine leaves the case app.** `apps/ai` holds the chat, the
  agent and its tools, the context builders, the conversation models and
  the Claude Desktop API over a matter; `apps/llm` holds the Anthropic
  and Gemini clients, embeddings, pricing and the cross-process status
  store, and knows nothing about matters. The semantic index stays with
  the content (`apps/case/semantic.py`, `MaterialChunk`). Tables keep
  their names; the moves are state-only migrations.
- **The case builder is `apps/case`, `apps/drive` and `apps/notes`.** The
  Library goes with the case builder: the practice side never uses the
  Note model. The three may import each other and the core (accounts,
  settings, management, matters, contacts, folders) and `apps/llm`, and
  nothing else.
- **The core never imports the case builder**, and the apps on top of it
  (`apps/ai`, `apps/mail`, `apps/drafts`) reach it only through
  `apps/case/models.py`, `apps/case/services.py`, the CourtListener
  client and the jurisdiction lists. The rule is four import-linter
  contracts in `pyproject.toml`, run by `uv run lint-imports` in CI.
  Direct imports are what is checked; tests and migrations are exempt.
  One seam is sanctioned by name: Settings > Integrations imports
  `apps/drive/google.py`, because that page is where Google is connected
  for the Drive mirror as for Gmail.
- **What crosses the boundary is registered, not imported.** The case
  shell renders the tabs registered in `apps/case/tabs.py` (the AI and
  Emails tabs register from their own AppConfigs); the semantic index
  takes material kinds the same way (emails register from `apps/mail`);
  the access middleware's matter lookups are registered by the apps
  that own the rows; the firm-wide search takes extra kinds through
  `apps/search/registry.py` (notes register there). The matter app
  sends `matter_closed` and the Drive mirror unlinks itself. The API
  token both MCP and the companion use is `accounts.ApiToken`.
- **Each feature can be switched off for the firm.** `Firm.case_file_enabled`
  and `Firm.library_enabled`, set by an administrator under Settings >
  Features, are read by the middleware (404 under `/case/` or `/notes/`),
  the sidebar, the matter header, the Notes tab and the firm-wide search;
  the Drive mirror pauses while the case file is off. The MCP matter API
  and the matter-scoped note routes stay up with the case file off, since
  the first serves practice data and the second belongs to the library.
  The data is never touched: switching off is how the firm retires the
  case builder before any code is removed.
- **The sidebar gains a Case entry**, after a rule below the practice
  pages, with Library beside it. Case opens `/case/`, which reopens the
  last matter on its last tab. The Detail/Case pills are gone from the
  matter header; the record and the case file link to each other through
  one link after the matter switcher, and the `mode-content` views that
  the pills swapped are gone with them.

This supersedes [The "two shells" redesign is abandoned
(2026-10-05)](2026-10-05-two-shells-redesign-abandoned.md). That record
refused a second sidebar and a shell switch; this one gives the case
builder sidebar entries of its own inside the one sidebar, and no
switch.

## Alternatives

- **Two repositories, two databases and an API between them**, with
  shared sign-in. This was the opening proposal. It was set aside, not
  refused: it is the right shape when a component scales differently or
  has a second consumer, and here it would be paid for by one person on
  a component used less, in two deploys, two migration streams,
  cross-service auth, no joins, and duplicated shell and theming. Git
  already preserves the work, and `git filter-repo` can carve the case
  builder's directories out with their history whenever that is wanted.
  The module boundary this record draws is what any such split would
  need first; the services module is what would become the client.
- **Splitting the repository without splitting the runtime**: the case
  builder as an installable package the practice manager pins. Deferred;
  it follows from this record without further untangling.
- **Leaving the AI engine in the case app** and drawing the boundary
  around it. Rejected: the engine is the firm's language-model layer,
  used by intakes, tasks, notes, mail and drafts, and the case builder
  is only one of its subjects.
- **Keeping the mode pills** beside the new sidebar entry. Rejected as
  two ways to the same place; the single cross-link in the header keeps
  the one thing the pills did that the sidebar cannot, which is going to
  this matter's case file.

## Consequences

- A new tab of the case shell is a `Tab` registered from an AppConfig
  (`apps/ai/apps.py` is the model), not an `elif` in `apps/case/views.py`
  or a line in `case-nav.html`. A new kind of material for the semantic
  index is `register_semantic_kind`; a new kind in the firm-wide search
  is `register_kind` in `apps/search/registry.py`; a new matter-scoped
  id in a URL is `register_matter_lookup`.
- A practice-side app that needs something from the case builder asks
  `apps/case/services.py` for it; if it is not there, add it there. The
  contracts fail the build otherwise.
- The AI tab's URLs are in the `ai` namespace (`ai:index`,
  `ai:conversation-view`, ...), the Emails tab's in `mail`, the draft
  links' in `drafts`; the paths did not change, so bookmarks, the MCP
  client and the companion extension go on working.
- `apps/case/registrations.py` is where the case app's own tabs, kinds
  and lookups are registered; reading it is how to learn what the shell
  shows.
- Retiring the case builder later means removing the three apps, their
  registrations and the sidebar entries, and writing the table-dropping
  migration; nothing on the practice side imports them.

## Evidence

- The owner's request of 2026-10-19 and the direction that the Library
  belongs with the case builder.
- `pyproject.toml`, `[tool.importlinter]`: the four contracts, all kept.
- `apps/case/tabs.py`, `apps/case/registrations.py`,
  `apps/case/services.py`, `apps/search/registry.py`,
  `apps/accounts/access.py` (`register_matter_lookup`),
  `apps/matters/signals.py`.
- The state-only migrations `ai.0001_move_ai_models`,
  `case.0095_move_ai_models`, `drafts.0004_move_ai_models`,
  `accounts.0024_api_token`, `drafts.0005_api_token`.
- `templates/sidebar.html` (the Case entry and the rule) and
  `templates/matters/includes/header.html` (the cross-link).

## Related

- [Architecture](../dev/architecture.md): The practice shell and the case builder; Module boundaries.
- [Case building](../dev/subsystems/case-building.md): The shell.
- [The "two shells" redesign is abandoned (2026-10-05)](2026-10-05-two-shells-redesign-abandoned.md), superseded.
- [Matter membership is enforced from the URL](2026-10-01-matter-membership-from-the-url.md).
