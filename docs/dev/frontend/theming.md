# CSS theming (light and dark)

Theming is **token-first**, with **co-located structural overrides**.

There are **seven themes**. Four are light: `light` (Matcha), `basic`
(after the 2017 LawPay UI: white ground, navy buttons, azure accents;
formerly `oxford`, and the `--oxford-*` palette keeps the source name),
`nord-light` (Nord's Snow Storm surfaces, Polar Night text, frost blue
links, frost cyan selection) and `letterhead` (after a firm engagement
letter: bone paper, hairline rules, fountain-pen blue). Three are dark:
`dark` (Gruvbox), `cosmic` (Nord) and `everforest` (green-gray surfaces,
cream text, signature-green links).

**Cosmic and everforest are the dark theme structurally.** They share the
dark token block and every dark structural rule, and only repoint the
`--gb-*` ramp (theme blocks in `colors.css`, palettes in `palette.css`).
Consequence: every "dark" selector is scoped to **all three** themes as
`:is([data-theme="dark"], [data-theme="cosmic"], [data-theme="everforest"])`.
When you add a new dark structural rule, use that `:is(...)` selector so
all the darks stay in sync.

**The non-Matcha lights are the light theme structurally.** They inherit
every `:root` (light) default and their blocks in `colors.css` only
repoint colour tokens. Light structural rules are the unscoped defaults,
so they get them for free; a rule scoped to `[data-theme="light"]` alone
does NOT apply to them. Scope to
`:is([data-theme="light"], [data-theme="nord-light"], [data-theme="basic"], [data-theme="letterhead"])`
(or the subset that needs it) when a light structural rule must reach the
other light themes. Retired themes: `sky`, `kosmos`, `kosmos-dark`,
`latte`, `mocha`, `everforest-light`; renamed: `oxford` to `basic`
(`theme.js` migrates stored settings).

All theme colour variables are authored in **oklch** (`palette.css` ramps and
any literal colours in `colors.css` theme blocks): no hex. Derivation
formulas (`color-mix`) and component styles consume tokens as before.

- **Tokens are the primary mechanism.** `static/css/colors.css` defines every
  semantic token in `:root` (light values) and re-defines the same tokens in a
  single `:is([data-theme="dark"], [data-theme="cosmic"], [data-theme="everforest"]) { … }` block (dark
  `gb-*` values). Component stylesheets consume `var(--token)` and are
  theme-agnostic: they flip automatically when the tokens change underneath
  them.

- **When dark only needs a different value → change a token.** Add or repoint
  the token in the `[data-theme="dark"]` block of `colors.css`. Do not write a
  scoped rule for a plain colour swap.

- **When dark needs a structurally different rule → scoped + co-located.**
  Some changes can't be a value swap because the colour moves to a *different
  property* (e.g. filled → outline buttons/badges: background drops out and the
  hue moves onto border + text; or task accent rails vs row fills). Those need a
  real rule. Put it in a `[data-theme="dark"] .component { … }` block at the
  **bottom of that component's own CSS file**, under a `Dark mode —` comment
  header. Keep the **colour decision in a token** (see the `--label-*-line`
  tokens for an example) and only the **structural rule** in the component.

- **Tokens are for decisions; derivations are for relationships.** A colour
  someone *chose* (link hue, selection wash, urgency) is a per-theme token.
  A colour that exists only in service of another colour (the border of a
  fill, the focus ring of an accent, a hover step) is a `color-mix()`
  formula off its source. Formulas cannot forget a theme, which is how
  fixed button borders rotted invisibly in eight themes. Current
  derivations: `--focus-ring` (accent normalized to mid-tone),
  `--field-focus` (ring diluted toward the field ground), the focus halo,
  and the modal button borders (fill mixed 20% toward `--color-darker`:
  darkens in light themes, lightens in dark ones). A theme may still
  override a derived value with a scoped rule as an escape hatch.

- **The brand is a two-token gradient.** The sidebar wordmark and kappa, the
  mobile topbar wordmark, the auth-card wordmark, and the painted favicon
  all run from `--brand-grad-from` to `--brand-grad-to`. The leading (left)
  end is `--brand-ink`, the stronger colour (set once in `:root`); the far
  end is the per-theme decision: each light block sets `--brand-grad-to`,
  and the darks get it by repointing `--gb-bright-yellow`. A new theme must
  set it (or set it to `var(--brand-ink)` for a flat brand), or it inherits
  Matcha's violet. The inline cuts fill from the shared SVG gradients in
  `templates/components/kosmos-brand-gradients.html`. The favicon is painted
  by `theme.js` on every page that carries `data-favicon`, the logged-out
  and error pages included; on dev (`data-favicon="brand-dev"`) `--nord11`
  red leads the gradient in place of the brand ink.

- **Do not create a monolithic `dark.css`.** Co-location keeps each component's
  light and dark story in one file. The only thing centralized is the token
  block in `colors.css`.

Files with co-located dark (shared by all three darks) blocks include `buttons.css`,
`badges.css`, `sidebar.css`, `detail.css`, `interface.css`, `viewer.css`,
`apps/tasks.css`, `apps/calendar.css`, `apps/matters.css`,
`apps/case/ai.css`, `apps/case/highlights.css`, `apps/notes-editor.css`. Grep
`:is([data-theme="dark"], [data-theme="cosmic"], [data-theme="everforest"])` for the authoritative list.

Related: never use a new `font-size` below `1rem`. The smaller sizes
already in the stylesheets are deliberate exceptions (the calendar's month
event chips, `.btn-sm`, badges and other dense chrome). Leave them as they
are; do not raise them to the floor.
