# One category per time entry, folder-style, not labels (2026-07-16)

From March 2026 time and expense entries could carry any number of
labels (`ActivityLabel`, a many-to-many with a colour and a badge). The
labels were meant to group work for a fee claim: the court exhibit for an
attorney-fee motion lists the time under each head of work with
subtotals and a grand total. A label system cannot produce that exhibit
cleanly, because an entry under two labels is counted twice, and the
code had grown a set of conflict guards to stop it.

## Decision

Each time or expense entry lives in exactly one category of its own
matter, or none. `ActivityCategory` is "a matter's coding buckets for
activity, like accounting transaction codes, each entry lives in exactly
one category (or none)". It belongs to one matter, is unique per matter
by name, carries a `claimed` flag and a drag-set `position`; "claimed
categories become the sections of the matter's Fee Claim Report". Flat
fees have no category.

The assignment is a dropdown. The views module says why: because an entry
belongs to at most one category, "assignment is a plain dropdown, not a
label-style apply modal, and no double-counting guards are needed
anywhere". `set_category()` looks the category up "scoped to the entry's
matter so a foreign category can't be set", and is allowed on a
billing-locked entry because it "never touches invoiced amounts".

Categories look like folders, not tags. The badge and colour were dropped
on the same day: "Categories are folders, not labels, the UI now says so."
The entry tables show the plain category name in a column with a
tasks-style dropdown to switch; the colour field is gone from the model.

## Alternatives

- **Labels (many-to-many).** Lived from 2026-03-12 to 2026-07-16, about
  four months. It lost because one entry under two labels is counted
  twice in any per-label total, so the fee claim needed guards that the
  one-category model makes unnecessary ("all label-era conflict guards
  deleted"). Existing data was migrated in `0014_categories_rebuild`.
- **Coloured badges on the category.** Shipped in the first cut on
  2026-07-16 and removed the same day with the folder-style column. The
  commit gives the design reason (folders, not labels), nothing more.
- **Firm-wide categories.** Not taken: a category is scoped to its
  matter, because the heads of a fee claim are the matter's own.

## Consequences

- Do not rebuild a multi-label system for activity or a colour on
  categories. A need to code an entry two ways is a sign the categories
  are drawn wrong for that matter, not that the model needs a second
  foreign key.
- `TimeEntry.category` and `ExpenseEntry.activity_category` are the two
  fields; the expense one is named differently because
  `ExpenseEntry.category` is the free-text descriptor printed on
  invoices.
- `Matter.uncategorized_claimed` decides whether uncoded time joins the
  claimed total; it is matter-level "so the whole team sees the same
  rollup".
- Bulk comp and matter moves skip entries locked on a finalized invoice;
  coding does not, by design.

## Evidence

- `apps/activity/models.py`, `ActivityCategory` docstring and the
  `uniq_category_name_per_matter` constraint.
- `apps/activity/categories/views.py`, module docstring and
  `set_category()`.
- `apps/activity/migrations/`, from
  `0008_historicalactivitylabel_activitylabel_and_more.py` to
  `0015_remove_activitycategory_color_and_more.py`.
- Commits: "feat: time and expense entries labels (#396)" (2026-03-12);
  "feat(categories): matter-scoped activity categories + Fee Claim
  Report" (2026-07-16, "One-category-per-entry makes double-counting
  structurally impossible"); "feat(categories): folder-style category
  column; drop badges and colors" (2026-07-16).

## Related

- [Time and billing](../dev/subsystems/time-and-billing.md), "Entries"
  and "Categories".
