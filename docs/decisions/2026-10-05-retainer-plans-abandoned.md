# Retainer plans are abandoned; the billing arrangement stays per matter (2026-10-05)

A "retainer plan" was a client-level billing arrangement: a flat fee per
period with a pool of included hours that every matter for that client
would draw down. It was designed in 2026 but never entered this
repository: there is no app, model, field, migration or commit for a
client-level fee, an included-hours pool or anything named "retainer
plan". The developer guide, written in October 2026, found that absence
and asked the owner whether the design was still planned.

## Decision

On 2026-10-05 the owner confirmed that retainer plans are abandoned and
are not to be rebuilt.

The billing arrangement is per matter and consists of three fields on
`Matter`: `billing_type` (`HOURLY` or `FLAT_FEE`), `flat_fee_amount`, and
`deferred_fees`, whose comment reads "fees accrue but are not currently
collectible, and the retainer is waived". A flat-fee matter bills by
`FlatFeeEntry` rows, one per fee or per period: the 2026-04-30 commit that
introduced them says "a one-time project fee is just one entry and a
monthly retainer is one entry per period, no cron required". Strict mode
keeps each matter's type clean: an hourly matter refuses flat-fee entries
and a flat-fee matter refuses time entries.

The word "retainer" survives in two places only: the trust balance a
client holds, printed as Retainer Balance on an invoice, and the wording
of trust deposit requests. Neither is a plan.

## Alternatives

- **A client-level plan with an included-hours pool.** The abandoned
  design. Its reasons for losing are not recorded in the repository; the
  owner's statement is the evidence.
- **Flat fees as a scheduled charge.** Rejected when flat-fee matters
  were built: a recurring fee is one `FlatFeeEntry` per period, entered
  like any other work, so that it joins invoices, the ledger and the
  Work in Progress tab through the same paths as time and expenses.

## Consequences

- Do not add a client-level billing model, an hours pool, or a plan
  table. A client who pays a monthly amount is a flat-fee matter with one
  entry per month, or an hourly matter whose client holds funds in trust.
- "Retainer" in code and copy means money in trust. A new feature that
  needs a word for a recurring flat fee should not reuse it.
- Trust available, the low-trust watch list and the dashboard already
  express the "is the client covered" question for hourly work; a pooled
  plan would have duplicated them.
- The architecture page's one-line summary of the billing subsystem still
  lists "the retainer plans" among its contents; that is stale and should
  be corrected, not implemented.

## Evidence

- The owner's statement of 2026-10-05, recorded in the shared brief for
  these records; nothing in the repository implements the design.
- `apps/matters/models.py`, `billing_type`, `flat_fee_amount` and the
  `deferred_fees` comment.
- `apps/activity/flat_fees/models.py`, `FlatFeeEntry`;
  `apps/activity/flat_fees/forms.py`, `clean_matter()`.
- Commit: "feat: flat-fee matters with FlatFeeEntry billing model"
  (2026-04-30).
- [Time and billing](../dev/subsystems/time-and-billing.md), "Retainer
  plans": "There is no retainer plan code in this repository".

## Related

- [Time and billing](../dev/subsystems/time-and-billing.md), "Data
  model".
- [Trust available is client-level and pending](2026-07-03-trust-available-client-level-pending.md),
  for what the application does instead with a client's retainer.
