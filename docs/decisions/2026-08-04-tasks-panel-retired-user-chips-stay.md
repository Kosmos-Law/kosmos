# Tasks panel retired, user chips stay (2026-08-04)

The Tasks tab filters by user and by date through its toolbar. In early
August 2026 two changes to that toolbar were tried in the same week. One
was a "panel" layout, opt-in per user under Settings, Appearance: a rail
of All, Admin and the open matters beside the list, driving the matter
filter, with Matters and Users sub-tabs and a Due tab added over the
next two days. The other was a row of one-click user chips in place of
the toolbar's user dropdown.

## Decision

The panel is gone and the chips stay.

- The classic list is the only layout. The `tasks_layout` field, the
  Settings section, the panel endpoints, the `no_matter` filter, the
  panel branches of `list.html` and the panel CSS were removed
  (migration `accounts 0015`).
- Users are filtered by monogram chips (All plus users) with a visible
  active state. Each viewer pins their own working set,
  `CustomUser.task_user_chips`, capped at `TASK_CHIPS_CAP` (5) and
  enforced at the toggle endpoint. An empty set means no explicit picks:
  a firm with five or fewer active users shows everyone, a larger one
  starts with no chips and pins from the overflow menu. A user filtered
  but not pinned is appended as a lit chip, so the active filter always
  reads. The same chip row and the same pinned set serve the three
  Activity tabs.

## Alternatives

The panel lived from 2026-08-02 to 2026-08-04. It lost because it hid
the user and date filter state behind whichever sub-tab was inactive,
because filtering by matter is rare on the firm-wide tab (the matter's
own Tasks tab covers it), and because the chips had solved user
switching, which was the panel's other job. A current-view strip that
pinned the active filters under the panel tabs was tried and reverted
the same day (2026-08-03).

## Consequences

- Do not rebuild a matter rail or a per-user layout setting on the Tasks
  tab; the matter Tasks tab is the matter view.
- The pinned set is one per viewer, shared by Tasks and Activity, so a
  pin made on one tab shows on the others. `toggle_chip_pin()` in
  `apps/tasks/tasks.py` is the one writer.
- The cap is a constant. A firm larger than five that wants more chips
  changes `TASK_CHIPS_CAP`, not the model.
- The `u` / `U` shortcuts that cycle the user filter and the filter
  modal's user field were untouched by the change and still work.

## Evidence

- Commit "refactor(tasks): retire the panel layout" (2026-08-04):
  "Classic wins: the panel hid user/date filter state behind inactive
  tabs, matter filtering is rare (matter detail covers it), and the chips
  now solve user switching."
- Commit "feat(tasks): user filter chips replace the toolbar user
  dropdown" (2026-08-04): "each viewer can pin a working set (max 5,
  CustomUser.task_user_chips) from an overflow menu ... small firms (<= 5
  active users) get all users as chips with zero setup."
- Commit "feat(tasks): opt-in matters panel layout for the list view"
  (2026-08-02) and the panel commits of 2026-08-02 and 2026-08-03,
  including the reverted current-view strip.
- Commit "feat(activity): semantic date presets + user chips on all three
  tabs" (2026-08-07): "The pinned set stays one per viewer."
- `apps/accounts/models.py`, the comment on `task_user_chips`;
  `get_user_chips()` and `TASK_CHIPS_CAP` in `apps/tasks/tasks.py`;
  `templates/components/user-chips.html`.

## Related

- [Tasks and calendar](../dev/subsystems/tasks-and-calendar.md).
- [Semantic date presets](2026-08-07-semantic-date-presets.md), the other
  toolbar mechanism ported to Activity in the same commit.
