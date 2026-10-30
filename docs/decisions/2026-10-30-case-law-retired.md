# Saved case law is retired

**Date:** 2026-10-30
**Status:** Accepted

## Context

Saved case law was the last of the research features. The Research chat
went in August, the Research tab in October, and
[the AI chat](2026-10-30-ai-chat-retired.md) this morning, taking the
agent's CourtListener tools with it. What remained was a Case Law tab on
each matter: a case added by citation, resolved on CourtListener, read
in a viewer that rendered CourtListener's HTML, highlighted, labelled,
summarised by the AI, and gated by a Research permission. It needed a
CourtListener token, a client with its own request throttle, a table of
state courts, a second source for the `Highlight` model, and a second
branch in every view and template that showed a highlight.

The firm had 31 cases saved across 11 matters, the newest in July, and
no highlights on any of them. Research now happens in Claude, which
reads CourtListener directly and keeps what it finds in the matter's
folder, where the firm's other files are.

## Decision

Saved case law is retired. The `CaseLaw` table is dropped, the
CourtListener client and the jurisdiction lists go, the Case Law tab and
its viewer go, and a highlight has one source: a document. The Research
permission is removed with the only thing it gated. The citation
vetting readers (the badges and modal the retired chat's archive used)
go too, since nothing wrote or showed them any more.

The 31 cases were exported before the table was dropped, to the Files
folder on the office server, as a record of what was saved where.

## Consequences

- `COURTLISTENER_API_KEY` is read by nothing; remove it from `config/.env`
  on each server when convenient.
- `Highlight.document` is required. The `caselaw` and `char_offset`
  columns and the `highlight_has_one_source` constraint are dropped.
  The Highlights tab loses its source filter (Cases / Documents), which
  had one value left.
- `perm_research` is dropped from `CustomUser`; the Permissions page has
  four switches.
- The case builder's public surface is `apps/case/models.py` and
  `apps/case/services.py`; the import contracts no longer name
  `courtlistener` or `jurisdictions`.
- [The case-law viewer renders CourtListener's HTML unsanitised](2026-10-02-opinion-html-rendered-as-is.md),
  [The Research tab is retired](2026-10-06-research-tab-retired.md) and
  [The user picks which cases a research run reads](2026-08-18-research-selection-gate.md)
  describe code that no longer exists.
