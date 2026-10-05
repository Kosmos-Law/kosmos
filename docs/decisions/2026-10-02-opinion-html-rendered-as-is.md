# The case-law viewer renders CourtListener's HTML unsanitised (2026-10-02)

In October 2026, while the user guide was being written, the two
viewers were found to print untrusted text into a `<script>` with
`|safe`: a highlight's text is whatever was selected in a PDF from
outside the firm, so a document containing `</script>` ended the script
and ran what followed for everyone who opened it. The same review found
the research results printing a case-law excerpt with `|safe`. Both were
fixed on 2026-10-02. The third `|safe` in that neighbourhood, the
opinion body in the case-law viewer, was looked at and left.

## Decision

`templates/case/caselaw-viewer.html` renders `opinion_html` (the
`html_with_citations` field CourtListener returns for an opinion, or the
legacy `CaseLaw.html` where one is stored) with `|safe`, as it is. The
markup is CourtListener's own, fetched on demand from their API by
`fetch_opinion()`; it is not user input and not content the firm's
counterparties author. The viewer's highlights depend on that markup:
each case-law highlight stores a `char_offset` and its text, and the
page script walks the rendered text nodes to place it, so a sanitiser
that rewrote or dropped elements would move or lose existing highlights.

This is a known exception, kept on purpose, with a real sanitiser as
the eventual answer: an allow-list of CourtListener's own elements and
attributes, applied in a way that keeps the text node sequence the
highlights anchor on.

## Alternatives

- **Escape it** (`{{ opinion_html }}`): the opinion would render as
  source text; the plain-text fallback (`opinion_text` in a `<pre>`)
  already exists for an opinion with no HTML and reads worse.
- **Strip tags to text**: loses the citation links CourtListener
  embeds, the paragraph structure and the anchors of every highlight
  already saved on a case.
- **Sanitise now with a generic library**: not done in the hardening
  pass, which was scoped to the two places where the firm's own
  material could run. No commit records trying it; the risk of
  disturbing saved highlights is the stated concern on the developer
  guide page.

## Consequences

- Trust in the source is the control. Any change to how opinions are
  fetched (another provider, a cache, a user-supplied opinion file)
  must either keep that trust or add the sanitiser first.
- Highlights on case law anchor on text offsets in CourtListener's
  markup. A sanitiser, when written, must preserve the text content and
  order of the rendered nodes, or re-anchor saved highlights.
- The other two `|safe` uses in the viewer (`highlights_json`,
  `importance_names_json`) are safe by construction: they go through
  `json_for_script()`, which escapes what HTML reads. Keep new script
  data on that path.
- The research results keep the `<mark>` tags of an excerpt and show
  the rest as text (`marked_excerpt`); that is the pattern for any new
  excerpt from the service.

## Evidence

- `templates/case/caselaw-viewer.html`: `{{ opinion_html|safe }}`, and
  the script that builds the combined text of the opinion's text nodes
  to place a highlight by its stored text and `char_offset`.
- `apps/case/caselaws/views.py`, `caselaw_viewer()`: `opinion_html`
  comes from `CaseLaw.html` or `fetch_opinion().html_with_citations`.
- `utils/safe_json.py`, `json_for_script()`.
- `docs/dev/subsystems/case-building.md`, "Saved cases": "That is a
  known decision: the markup is CourtListener's, the viewer anchors
  highlights on it, and when the viewers were hardened in October 2026
  ... this one was left as it is pending a real sanitiser."
- Commit: "fix(security): highlight text and case-law excerpts cannot
  run in the viewers" (2026-10-02), which hardened the other two and
  did not touch the opinion body.

## Related

- [Case building](../dev/subsystems/case-building.md), "The viewer",
  "Saved cases" and "Things that bite".
- [Research tab pipeline](../dev/subsystems/ai/research-tab.md).
