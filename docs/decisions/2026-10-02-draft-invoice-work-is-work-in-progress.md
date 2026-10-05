# Work on a draft invoice is work in progress, not unbilled (2026-10-02)

An invoice gathers a matter's unbilled entries the moment it is created as
a draft, by pointing each entry's `invoice` foreign key at it. Until
October 2026 that act also took the entries out of every figure the
application reported: the ledger's Total Cost to Date, the matter
overview and trust available all counted "unbilled" work, and a draft is
not a ledger charge, so the work vanished from all of them until the
invoice was sent. A firm that drafted its invoices early looked, for days,
as if the work had never been done.

## Decision

A draft or approved invoice is a pre-bill, not a receivable. Its work stays
work in progress until the invoice is issued, and it stays out of the
invoicing queue, because it is already on an invoice.

`Matter.value` carries both figures: `unbilled`, "the invoicing queue. Not
the whole of work in progress", and `work_in_progress`, "everything not yet
billed: the invoicing queue plus the drafts, net of the discounts already
set on those drafts". `drafted` is the difference, "entries on invoices not
yet issued (DRAFT/APPROVED). Off the invoicing queue, but still work in
progress until the invoice is sent." `UNSENT_STATUSES = ("DRAFT",
"APPROVED")` in the invoice model is the set every consumer imports, with
the rule beside it: "Work on these invoices is still work in progress, not
a receivable: it stays out of the ledger and balance due."

## Alternatives

Before the change the ledger, the overview and trust available read the
unbilled figure alone. That was not a design so much as the first figure
to exist; the commit records the effect ("the work dropped out of Total
Cost to Date and out of trust available until the invoice was sent") and
replaced it. Counting drafts as billed was not considered: a draft can be
edited, re-swept or deleted, and nothing is owed on it.

## Consequences

Three figures are all called work in progress, and they differ on purpose.
The dashboard and the Work in Progress report count unbilled time only
(`_wip_base()` in the WIP aggregation; the dashboard defaults to this
month). The Work in Progress tab and the Add Invoice form use the
invoicing queue, `Matter.value["unbilled"]`, with expenses and flat fees.
The ledger, the matter overview, trust available, the dashboard's
low-trust watch list, the AI ledger section and the realization report
count drafts too. The commit left the first two alone: "The invoicing
queue (unbilled) and the WIP report are unchanged."

Anything new that reports what a matter is owed or has accrued should read
`work_in_progress`, not `unbilled`, and should test with an open draft.
The realization report files the fees on an unsent invoice under Unbilled
(WIP), "as everywhere else in Kosmos"; before 2026-10-02 it counted them
as Outstanding. The trust figure follows the same rule so that "a matter's
trust available does not jump while a draft is open".

## Evidence

- `apps/matters/models.py`, the `unbilled`, `drafted` and
  `work_in_progress` comments in `Matter.value`.
- `apps/invoicing/invoices/models.py`, the comment on `UNSENT_STATUSES`.
- `apps/trust/available.py`, `_unbilled_by_client()`: "Work on a
  DRAFT/APPROVED invoice counts, net of that invoice's discount: it has
  left the invoicing queue but isn't owed until the invoice is sent, and
  would otherwise drop out of trust available while the draft is open."
- `apps/reports/realization/aggregation.py`, the `unsent` fact: "A draft
  or approved invoice has not been sent: its work is still work in
  progress, as everywhere else in Kosmos."
- Commits: "ledger: count work on draft invoices as work in progress"
  (2026-10-02); "fix(money): trust payments, payment edits, returned
  money and the figures that report them" (2026-10-02), the realization
  paragraph.

## Related

- [Time and billing](../dev/subsystems/time-and-billing.md), "Work in
  progress" and "Reports".
- [Trust available is client-level and pending](2026-07-03-trust-available-client-level-pending.md).
