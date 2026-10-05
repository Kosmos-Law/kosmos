# Visibility and polling inside htmx swaps (2026-07-29)

Two bugs in the summer of 2026 came from the same place: assuming that
an htmx swap replaces an element and leaves it alone. In July, after a
note was saved on an intake, the detail region re-rendered and the
Forms pane appeared inside the notes list; only some panes leaked, and a
full page load never reproduced it. In August the AI status indicator,
newly swapped with idiomorph to stop a per-second flicker, polled once
and froze while the worker kept running unheard, and on pages without
idiomorph the finished reply landed inside the indicator and the poll
ran on, posting "interrupted" once a second.

## Decision

Visibility inside a swapped region is driven by a class on a container
that has no `id`, with CSS doing the showing and hiding. htmx's settle
phase snapshots the attributes of every element whose `id` matched one
before the swap and re-applies them a moment later; an inline `style`
that Alpine's `x-show` wrote on such an element in that window is wiped,
while id-less siblings keep theirs. So `x-show` does not go on an
element that is also an `hx-target`; Alpine binds `:class="'pane-' +
pane"` on the id-less container and the stylesheet carries the rules.

A poller that swaps itself with `hx-swap="morph"` uses a standing
`hx-trigger="every 1s"` with `hx-sync="this:drop"`, not a `load`
trigger with a delay. Morph preserves the element, so a load-triggered
chain fires once and stops. The interval ends when the terminal
response answers with a different root element, and every terminal
response also carries `HX-Reswap: outerHTML` so the poller is replaced
even on a page where idiomorph is not loaded and htmx would fall back to
`innerHTML`. Every page that hosts the poller loads the idiomorph
script.

## Alternatives

- `x-show` with `x-cloak` on the panes, which is the Alpine default.
  Lived until 2026-07-29 and is what failed under settle.
- Giving the panes no `id`. The assessment pane is itself an
  `hx-target`, so its `id` has to stay, which is why the class moved to
  a container above the panes: "The container has no id, so settle
  never touches it."
- The `load delay:1s` polling chain. Lived from the first poller until
  2026-08-15, when the swap became a morph; it depended on every swap
  creating a fresh element.
- Ending the poll by an empty response under the same `id`. Rejected in
  the same commit: a same-id empty div is morphed in place and keeps
  the interval alive forever.
- Relying on morph alone to replace the root. Lived from 2026-08-15 to
  2026-08-23, when the intake chat window, which had never loaded
  idiomorph, showed what happens without it. `HX-Reswap` covers the
  page that forgets.

## Consequences

- When a swapped region shows and hides parts of itself, bind a class
  on an id-less wrapper and write the CSS. A symptom that only appears
  after a swap and never on a full load is this.
- A morphed out-of-band fragment must carry the same `class` and
  `hx-ext` as the standing element, or the next swap silently
  downgrades to `innerHTML`.
- A standalone page that includes `case/ai/status.html` must load
  idiomorph itself; `base.html` does, the standalone windows do each
  with a comment saying why.
- Do not add a second poller pattern. The comments on
  `templates/case/ai/status.html` and `chat-statusbar.html` are
  required reading before touching either.

## Evidence

- Commit "fix(intakes): pane visibility survives htmx settle; bare menu
  button" (2026-07-29): "htmx's settle phase restores attribute
  snapshots on id-matched elements ... wiping the display styles
  Alpine's x-show had just written - id-less elements kept theirs,
  which is why only some panes leaked. Visibility now rides a pane-*
  class Alpine binds on the id-less container."
- `templates/intakes/detail.html`, the `intake-main` container, and the
  `.pane-*` rules in `static/css/apps/intakes.css`.
- Commit "fix(ai): status polling died after the first morph"
  (2026-08-15): "morph preserves the element, so the chain stopped
  after one poll ... The indicator now polls on a standing 'every 1s'
  interval with hx-sync this:drop."
- Commit "fix(ai): a status poll can no longer write 'interrupted' on
  top of a delivered reply" (2026-08-23): "every terminal status
  response ... carries HX-Reswap: outerHTML so the poller is replaced
  whatever the page's swap support."
- `templates/case/ai/status.html`, the header comment; `_terminal()`
  and `_poll_ended()` in `apps/case/ai/views.py`.
- `docs/dev/conventions/htmx-alpine.md`, "The settle gotcha" and
  "idiomorph".

## Related

- [HTMX, Alpine and idiomorph](../dev/conventions/htmx-alpine.md)
- [Shared state lives in the database cache](2026-08-17-shared-state-in-the-database-cache.md)
