# The "two shells" redesign is abandoned (2026-10-05)

A matter is worked in a workspace with two modes: Detail, under
`/matters/<id>/`, is the matter's record (Overview, Contacts, Rates,
Activity, Events, Tasks, Proceedings, Settlement, Ledger), and Case,
under `/case/<id>/`, is the working file (Documents, Highlights,
Timeline, Witnesses, Notes, Emails, Labels, Search, AI, Research). The
two are switched by a pair of pills in the matter header, and both sit
inside the one firm-wide sidebar. In August 2026 a redesign was begun on
a branch named `two-shells`: a separate Case sidebar with its own
recent-matters switcher and the case tabs as its primary list, the
Practice sidebar keeping the firm-wide pages, and a Practice/Case switch
under the brand. The pills, `matter-base.html` and the mode-content
views were to go. The branch was never merged and is not in the
repository; the history was rewritten in October 2026 and it did not
survive.

## Decision

The redesign is abandoned and is not to be rebuilt. The owner said so
on 2026-10-05. The matter workspace keeps its two modes behind the pills
in `templates/matters/includes/mode-pills.html`, both extending
`templates/matters/matter-base.html`, inside the one sidebar in
`templates/sidebar.html`.

## Alternatives

The redesign was the alternative. What is known of its motive comes from
the working notes of the time rather than the repository: the case
builder was felt to be hidden behind a pill pair inside a matter record,
and the notes editor's own shell was the precedent. The reason it was
dropped is not recorded.

## Consequences

- Do not reintroduce a second sidebar, a shell switch or a
  per-shell base template for the case workspace. New case tabs go in
  `templates/case/includes/case-nav.html` and new firm-wide pages in
  `templates/sidebar.html`.
- The pattern the architecture page describes is the live one: the
  sidebar is `hx-boost`ed into `#main-content`, mode switches swap
  `#mode-content`, tab switches swap `.detail-body`.
- The case shell's views gained `matter_access_required` during the
  October 2026 access audit, independently of the redesign; that is the
  live protection, not a shell boundary.

## Evidence

- The owner's statement of 2026-10-05 that the design is dropped. It is
  not in the repository; this record is where it is written down.
- `docs/dev/architecture.md`, "The two shells", describing the modes and
  the pills as they are.
- `templates/matters/includes/mode-pills.html`,
  `templates/matters/matter-base.html` and
  `templates/case/includes/case-nav.html`, all present on `dev`.
- Commits "fix(case): tab_content carries matter_access_required like the
  other shell views" and "docs(dev): the shell views carry
  matter_access_required" (2026-10-05).

## Related

- [Architecture](../dev/architecture.md): The two shells.
- [Matters, contacts and parties](../dev/subsystems/matters.md) and
  [Case building](../dev/subsystems/case-building.md): the two modes.
- [Matter membership is enforced from the URL](2026-10-01-matter-membership-from-the-url.md).
