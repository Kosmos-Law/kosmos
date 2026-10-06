# The Research tab is retired (2026-10-06)

The matter workspace had a **Research** tab for case-law research,
rebuilt on 2026-08-17 after the research chat mode was retired. A run
took a question through a fixed pipeline on qcluster: the model proposed
query variants (drawing on the firm's library notes) for the user to
approve, Kosmos searched CourtListener, the model triaged the
candidates, the user picked which cases to read at a selection gate,
each chosen case was briefed from its full opinion, citing cases and key
authorities were chased and briefed, high-rated cases got a
negative-treatment check, and Gemini Pro wrote the answer. Beside
**Search** the tab had **History**, **Validate** (forward citations of a
case with a treatment assessment of each), **Case Briefs** (saved
briefs) and **Full Cases** (the matter's saved case law).

## Decision

The tab and its pipeline are retired and are not to be rebuilt in the
same form. The owner judged it a very complicated feature whose
implementation was not good, and the agentic chat's CourtListener tools
(search, citation lookup, full-opinion reads, search inside opinions,
and the `save-caselaw` write) now cover research from inside a matter.

Saved case law stays, as a view of the **AI** tab: its toolbar has a
Conversations | Case Law switch, shown to admins and users with the
Research permission, and `/case/<id>/caselaws/` renders the list with
the AI tab active. It moved there because the agent is what finds and
saves cases now, so the cases sit beside the conversations that produce
them.

## What was removed

- The tab and its sub-views (Search, History, Validate, Case Briefs) in
  the case navigation, and the Full Cases sub-view as a part of it.
- The whole pipeline in `apps/case/research/`: the query refiner and
  `query_syntax.py` rules, library mining, triage, the case-selection
  gate, full-opinion briefing (`briefing.py`), the citing-case and
  key-authority chases, the negative-treatment check, the final answer,
  the stale-run reaper, and the views, models and CourtListener search
  helpers there.
- Its routes in `apps/case/urls.py`, `templates/case/research/`,
  `static/css/apps/research.css`, and its tests.
- The four research id lookups in `MATTER_LOOKUPS`
  (`apps/accounts/access.py`) and the `research` path in the
  `perm_research` pattern of `PermissionMiddleware`.

## What the migration deletes

`apps/case/migrations/0093_delete_research_tab.py` drops the four
models and their tables: `ResearchQuery` (every research question and
its answer), `ResearchResult` (the candidates and their briefs, triage
scores and treatment fields), `CaseBrief` (saved case briefs) and
`CitationVerification` (Validate's citing opinions and assessments).
Saved case law (`CaseLaw`) and its highlights are not touched.
Reversing the migration recreates the tables empty; none of the deleted
rows come back.

## What remains

- The Research permission (`perm_research`). It gates saved case law,
  the case-law viewer, and the agentic chat's CourtListener tools and
  `save-caselaw` protocol.
- The CourtListener client in `apps/case/courtlistener.py`, now also
  holding `search_opinions` and `sanitize_query`, and the process-wide
  request throttle in `apps/case/courtlistener_throttle.py`.
- The state court lists, moved to `apps/case/jurisdictions.py`.
- The 200-word summary of a saved case, moved to
  `apps/case/caselaws/tasks.py`.
- Adding a case by citation, the case-law viewer, highlights in
  opinions, and the AI context setting on saved cases.
- The rendering of old research chat answers (`research_trail`), which
  belongs to the earlier
  [Research chat (retired 2026-08-16)](research-chat-retired.md) and is
  unchanged.

Recoverable from git history at the parent of commit `c70da1a05`.

## Evidence

- Commit `c70da1a05`, "Remove the Research tab; saved case law becomes
  a view of the AI tab" (2026-10-06).
- The comment heading migration `0093`.
- `templates/case/ai/view-pills.html`, the Conversations | Case Law
  switch.

## Related

- [The user picks which cases a research run reads](2026-08-18-research-selection-gate.md)
  and [AI chat runs on threads, research runs on the
  queue](2026-08-17-chat-on-threads-research-on-the-queue.md): records
  about the retired pipeline.
- [Research chat (retired 2026-08-16)](research-chat-retired.md): the
  feature the tab replaced.
- [Agentic chat](../dev/subsystems/ai/agent-chat.md) and
  [Case building](../dev/subsystems/case-building.md#saved-cases).
