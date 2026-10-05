# Online payments: provisional until settled, and the processor switch (2026-06-25)

Online collection was built in June 2026 before any processor sandbox
existed, against a contract (`apps/invoicing/processors/base.py`) that
collapses every processor's native states onto six: `succeeded`,
`pending`, `failed`, `returned`, `refunded`, `voided`. Three questions had
to be settled then and were revisited as real processors arrived: what
the application runs when no processor is configured, when a charge
counts as paid, and what happens when accepted money later falls through.

## Decision

**The fake is a real processor, not a mock.** `FakeProcessor` simulates
the whole lifecycle in process ("card charges settle immediately; ACH
charges are accepted as PENDING, then later move to SUCCEEDED or
RETURNED") so that the pay page, recording and reconciliation could be
built end to end. It records a `Payment` through the same path as any
other processor, "although no money moved". It is the built-in default of
`PAYMENT_PROCESSOR`, "so development and the test suite run without any
processor credentials".

**`none` is what production runs until a processor is configured.** The
`DisabledProcessor` (2026-10-01) keeps the emailed links working,
"because they are also how a client downloads the invoice or statement",
shows the amount due and the documents, tells the client to contact the
firm, and "nothing can be charged or recorded". The installer sets it for
a production install because the built-in default would record a payment
with no money behind it.

**Accepted money is recorded at once, provisionally.** `ACCEPTED_STATUSES`
is `succeeded` and `pending`: "for card, the money is in; for ACH it is
provisional until SUCCEEDED, but the invoice shows as paid". A pending ACH
charge becomes a `Payment` applied in full, the invoice flips to `PAID`,
and `processor_status` is the only sign that it is provisional. The same
for a trust deposit, which is written with `confirmed=result.settled`,
"normally False at charge time (a card is merely captured, an ACH still in
flight)", and is confirmed by the reconciler once the processor reports
the funds deposited, "so the confirmed balance tracks the bank".

**Money that falls through is reversed, and the confirmed ledger is never
silently changed.** On `failed`, `returned` or `voided`: an operating
payment has its applications deleted one by one (so the invoices reopen)
and is deleted; a payment request it fulfilled goes back to Sent, since
"a payment request paid by money that then fell through is not paid"; an
unconfirmed trust deposit is deleted, its history row keeping the audit
trail; a deposit the firm already confirmed "is a trust shortfall: don't
silently mutate the confirmed ledger, flag its status and leave it for
staff to reconcile by hand". Staff are emailed either way, and the Trust
lists flag the row (`fell_through`).

## Alternatives

- **Record only on settlement.** Not taken; the design records a pending
  ACH "so the invoice shows paid provisionally" and relies on the webhook
  and the hourly `poll_pending()` backstop to reverse it. The reason for
  preferring provisional over deferred recording is not recorded beyond
  the base-module comments.
- **Delete a returned deposit whatever its state.** Rejected on
  2026-07-03 in favour of flagging a confirmed one. Email was the only
  signal until 2026-10-02, when the Returned flag was added to the Trust
  lists because that list "is empty by default".
- **No disabled processor.** Until 2026-10-01 an install either ran the
  fake or a real adapter; the documentation audit found the gap.

## Consequences

- A report that counts `PAID` invoices counts provisional ones.
- A refund made in the processor's portal is not reversed. `refund()` is
  on the contract and every adapter, but nothing calls it, and `refunded`
  is not in `REVERSED_STATUSES`, so a refund webhook only updates
  `processor_status`. Whether refunds should reverse automatically has not
  been decided; record the money movement by hand.
- A returned deposit that was confirmed keeps counting in every balance,
  pending and confirmed, until someone edits it: wrong on purpose until
  reconciled.
- Tests pin `PAYMENT_PROCESSOR="fake"`; a deployment must set `none` or
  a real adapter, never leave the default.

## Evidence

- `apps/invoicing/processors/base.py`, the status comments;
  `processors/fake.py` and `processors/none.py`, module docstrings;
  `processors/factory.py`, module docstring; `scripts/install.sh`.
- `apps/invoicing/pay/recording.py`, `record_payment()`;
  `apps/invoicing/pay/balance.py`, `record_trust_deposit()`.
- `apps/invoicing/pay/reconcile.py`: `_apply_to_deposit()`,
  `_reverse_payment()`, `_reverse_deposit()`, `_reopen_requests()`.
- `apps/trust/models.py`, `Transaction.fell_through`.
- Commits: "feat(invoicing): pluggable payment-processor abstraction +
  fake processor" and "feat(invoicing): record online payments +
  settlement/return reconciliation (Phase 2 Piece C)" (2026-06-25);
  "feat(pay): reconcile trust deposits on settlement/return webhooks"
  and "feat(trust): auto-confirm deposits when funds settle in the bank"
  (2026-07-03); "fix: close the operator gaps the documentation audit
  found" (2026-10-01); "fix(money): trust payments, payment edits,
  returned money and the figures that report them" (2026-10-02).

## Related

- [Trust and payments](../dev/subsystems/trust-and-payments.md), "Online
  payments" and "What does not exist".
- [Online payments](../admin/integrations/payments.md) in the operator
  guide.
