# Date presets are re-derived from their label on every read (2026-08-07)

The Tasks tab's date dropdown offers presets: Today, Next Workday, Next
7 Days, This Week, Next Week and so on. Each click stamped literal
dates into the session filter, and nothing ever re-stamped them.
Sessions outlive the day they were stamped on (file-backed on the
development server to survive its nightly database reload, an
eight-week cookie age everywhere), so the next morning the dropdown
still showed a lit Today while the query ran `date_due <= yesterday`,
hiding the tasks due today unless something was overdue. The bug was
intermittent by nature: one click on the dropdown re-stamped the date
and buried the evidence. The three Activity tabs had the same design,
each with its own hand-rolled recalculation, and the copies had drifted.

## Decision

The stored `filter_label` is the source of truth for a preset.
`refresh_date_preset()` in `apps/tasks/services.py` re-derives the date
bounds from today on every read of the filter (list, board, filter
modal, the matter Tasks tab), so "Today" means today however long ago
it was clicked. A custom range keeps its literal dates; the filter modal
still owns exact ranges, and `detect_filter_label()` promotes a posted
range that happens to match a preset window into that label, reporting
`custom` otherwise rather than mislabelling the state. The presets only
touch the date dimension, so a status chosen in the modal survives a
preset click.

The Activity tabs use the same function with their own vocabulary
(`apps/activity/presets.py`, backward-looking where the tasks presets
are forward-looking). Dates come from `timezone.localdate()`, never
`date.today()`.

## Alternatives

Re-stamping the dates on the dropdown click only was the state before,
and is the bug. Expiring the filter at midnight would have lost the
user's other filter choices. Keeping one copy of the recalculation per
tab was the Activity design and had already drifted (flat fees lacked
"last week" and "last month").

## Consequences

- A new preset is a line in `quick_date_filters()` (or the Activity
  vocabulary), nothing else; the Past Due preset of 2026-09-30 was added
  that way.
- Any new reader of a date filter must go through
  `refresh_date_preset()`; reading `filter_data` raw brings the stale
  dates back.
- `filter_label` is stored and compared as a slug; renaming a preset
  needs its old slug handled or stored sessions lose the preset.
- Weeks run Sunday to Saturday.

## Evidence

- Commit "fix(tasks): date presets become semantic; Today always means
  today" (2026-08-07): "The date dropdown's presets ... stamped literal
  dates into the session and nothing ever re-stamped them ... the next
  day the dropdown still showed a lit Today while the query ran date_due
  <= yesterday."
- Commit "feat(activity): semantic date presets + user chips on all three
  tabs" (2026-08-07): "The three tabs each carried a hand-rolled
  label-to-dates recalc (drifting copies ...). All of it collapses into
  apps/activity/presets.py."
- `refresh_date_preset()` docstring: "filter_label is the source of
  truth: when it names a quick preset, the stored date bounds are
  re-derived so 'Today' always means today, however long ago it was
  clicked."
- Commit "feat(tasks): Past Due preset in the date dropdown" (2026-09-30).

## Related

- [Tasks and calendar](../dev/subsystems/tasks-and-calendar.md): The
  semantic date presets.
- [Session state](../dev/conventions/session-state.md).
- [Tasks panel retired, user chips stay](2026-08-04-tasks-panel-retired-user-chips-stay.md).
