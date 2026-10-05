# A payment's side effects are changed through the payment, never by cascade (2026-10-02)

A payment by Trust is money leaving the client's trust account, so it has
two halves: the `Payment` on the matter and a `Withdrawal` on the trust
ledger. Until October 2026 the second half depended on which button opened
the form. The invoice's Pay from Trust button wrote a withdrawal, unlinked
and dated today; the Payments tab wrote none; an edit to the payment left
the withdrawal as it was. Deleting a payment or a credit, meanwhile,
removed its invoice applications by database cascade, which skipped the
hook that reopens the invoice: the invoice stayed Paid at $0.00 while the
matter's balance went up. These rules were settled with the firm's owner
while the user guide was being written.

## Decision

The module docstring of `apps/invoicing/payments/trust.py` is the rule: a
payment whose method is Trust "always has one matching withdrawal on the
trust ledger, and a payment by any other method never has one. The payment
and its withdrawal are linked (`Transaction.payment`): changing the
payment changes the withdrawal, and deleting the payment deletes it."
Every view that saves a payment calls `sync_trust_withdrawal()` in the
same transaction, and deletion calls `delete_trust_withdrawal()` first.

The link is `OneToOneField(on_delete=SET_NULL)`, not a cascade. The field
comment: "The two are one movement of money: deleting the payment on its
own screen deletes its withdrawal. That is done there, on purpose, and not
by a cascade: a trust ledger row must never disappear as a side effect (of
deleting a whole matter, say)." The Trust tab refuses to edit or delete a
withdrawal with `payment_id` set and points at the payment; it may still
be marked confirmed.

A trust payment "cannot be more than the client holds"
(`PaymentForm._check_trust_funds()`, against the pending balance excluding
the payment's own withdrawal) and is refused on a matter with no client.

The same owner's rules on every payment and credit: the form opened from
an invoice starts at "what is still owed, not the invoice's total: a
second payment on a part-paid invoice starts at the remainder"; an applied
payment "cannot shrink below what is applied, or move to another matter:
its applications would be left on invoices it no longer covers"; and
applications are never cascaded away. `delete_with_applications()` takes
them off one by one because "a cascade would remove the applications
without running their delete hook, and the invoices they paid would stay
Paid". A reopened invoice goes back to the status it was paid from, Sent
or Deferred, read from its history (`status_before_paid`).

## Alternatives

- **Cascade the withdrawal with the payment.** Shipped on 2026-10-02 in
  the first cut (migration trust 0006) and amended before release the same
  day: deleting a whole matter deleted its payments and, through the
  cascade, their withdrawals, "trust ledger rows vanishing as a side
  effect, and the client's balance rising".
- **A signal instead of an explicit call.** Not taken; every save site
  calls the sync. The reason a signal was not used is not recorded.
- **Reopen to Sent always.** The behaviour until 2026-10-05; a Deferred
  invoice whose payment was taken off came back as Sent.

## Consequences

- A new code path that creates or edits a `Payment` must call
  `sync_trust_withdrawal()` inside the same `transaction.atomic()`; it is
  a convention, not a signal.
- A payment removed any other way (with its whole matter) leaves its
  withdrawal on the ledger, unlinked. The matter side is not guarded; the
  contact side is (`Contact.deletion_blockers()`).
- Never delete applications with a queryset `delete()` on a live invoice;
  `_reverse_payment()` in the reconciler deletes them one at a time for
  the same reason. `Invoice.void()` is the accepted exception: the invoice
  is leaving the receivable statuses anyway.
- `reopen_if_no_longer_covered()` is the one place that decides whether an
  invoice is still covered; `amount_remaining` alone cannot, because a
  Paid invoice with no allocations counts as paid for legacy reasons.

## Evidence

- `apps/invoicing/payments/trust.py`, module docstring and
  `trust_balance()`.
- `apps/trust/models.py`, the comment on `Transaction.payment`;
  `apps/trust/views.py`, `_belongs_to_a_payment()`.
- `apps/invoicing/payments/forms.py`, `_check_against_applications()`,
  `_check_trust_funds()`; `apps/invoicing/invoices/views.py`,
  `quick_invoice_payment()`.
- `apps/invoicing/applications/models.py`, `delete_with_applications()`
  and `apply_to_invoice()`; `apps/invoicing/invoices/models.py`,
  `reopen_if_no_longer_covered()` and `status_before_paid`.
- Commits: "fix(invoicing): money actions need a POST, and removing a
  payment reopens its invoice" (2026-10-02); "fix(money): trust payments,
  payment edits, returned money and the figures that report them"
  (2026-10-02, "Decided with the firm's owner"); "fix(money): a payment's
  trust withdrawal is changed only through the payment; credits get the
  payment's edit checks" (2026-10-02); "fix(invoicing): a reopened
  invoice goes back to the status it was paid from" (2026-10-05).

## Related

- [Trust and payments](../dev/subsystems/trust-and-payments.md),
  "Recording a payment"; [Time and billing](../dev/subsystems/time-and-billing.md),
  "Applying credits and payments".
