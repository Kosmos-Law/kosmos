# Civil dates come from `timezone.localdate()` (2026-08-25)

The servers keep UTC and the firm does not. With `USE_TZ` on, Python's
`date.today()` and `timezone.now().date()` give the UTC calendar day,
which rolls over at about eight in the evening in the firm's time zone.
Most of the year that was invisible. On the last evening of a month it
inverted every month-to-date range (the dash's work in progress, the
activity and realization windows, the unbilled cutoffs), re-triggered
the once-a-day dash check-in, and stamped completed tasks with
tomorrow's date.

## Decision

A civil date (today, a default for a date field, the bounds of a
preset, a completion stamp) is `django.utils.timezone.localdate()`,
which converts the current instant to `TIME_ZONE` before taking the
date. `date.today()`, `datetime.now().date()` and
`timezone.now().date()` are wrong in application code, and one found
in review is a bug to fix, not a style point. Tests that build
today-relative fixtures use the same call.

## Alternatives

- Running the servers in the firm's time zone. Not taken; the reason is
  not recorded. The application already sets `TIME_ZONE` and `USE_TZ`,
  so the conversion belongs in the code, not in the host.
- Fixing the sites that had been noticed, one at a time. That is how it
  went until 2026-08-25: `date_completed` was fixed on 2026-08-03, the
  date presets on 2026-08-07, and the sweep of 2026-08-25 found the
  rest. Three more sites that the sweep missed (three invoicing forms
  and the bulk Create Invoices dialog, which used
  `timezone.now().date()`) were fixed on 2026-10-05, and the intake
  note stamp the same day.

## Consequences

- Grep for `date.today()` and `.now().date()` in a change before
  review; the correct spelling is `timezone.localdate()`. Both are
  wrong, and the second looks right. A few stragglers remain in the
  reports and the AI context at the time of writing; each is a bug.
- A form's default date is set in `__init__` from `localdate()`, so it
  is computed per request, not at import.
- The date presets store their name and re-derive their bounds from
  `localdate()` on every read, so the stored session never holds a
  stale "today".
- Anything that compares a stored date with "today" (overdue, past due,
  the month to date) must take today the same way, or the two disagree
  for four hours a day.

## Evidence

- Commit "fix: derive civil dates from timezone.localdate(), not naive
  date.today()" (2026-08-25): "With USE_TZ and a UTC server clock,
  date.today() rolls to the next civil day at ~8pm ET. On the last
  evening of a month that inverted every month-to-date range ... and
  re-triggered the daily dash check-in. Sweep all app code to
  timezone.localdate()."
- Commit "fix(tasks): stamp date_completed with the local date, not
  UTC" (2026-08-03).
- Commit "fix(tasks): date presets become semantic; Today always means
  today" (2026-08-07).
- Commit "fix(invoicing): default form dates to today in the firm's
  time zone" (2026-10-05): "both the server's clock, so late in the
  evening the default was already tomorrow."
- `docs/dev/conventions/session-state.md`, "Things that bite": "Dates
  come from `timezone.localdate()`, never `date.today()`."

## Related

- [Session state](../dev/conventions/session-state.md), "Semantic date
  presets"
- [Time and billing](../dev/subsystems/time-and-billing.md)
- [Tasks and calendar](../dev/subsystems/tasks-and-calendar.md)
