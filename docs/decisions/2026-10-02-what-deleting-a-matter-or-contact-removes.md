# What deleting a matter or a contact removes (2026-10-02)

Almost everything that points at a matter cascades when the matter is
deleted. Two foreign keys do not follow that pattern, and both were
found while writing the user guide. `Invoice.matter` is `SET_NULL`, so
deleting a matter left its invoices behind with no matter, no entries
and no payments, though the confirmation dialog counted them among what
would go. `Transaction.contact` (the trust ledger) is `CASCADE`, so
deleting a contact silently deleted the client's trust ledger and trust
deposit requests, and detached the contact from every matter it was the
client of, on a one-line "delete this record?" prompt.

## Decision

- Deleting a matter (admin-only) deletes the matter's invoices
  explicitly, in the same transaction, before the cascade runs. The
  `SET_NULL` on `Invoice.matter` stays; the view does what the database
  would not. Trust `Transaction` rows belong to the contact, not the
  matter, and are untouched.
- A contact cannot be deleted while `Contact.deletion_blockers()` returns
  anything: while it is the client on a matter, has trust activity, or
  has trust deposit requests. The contact delete view and the folder
  delete view both call it and refuse with the reason; deleting a folder
  and its contacts keeps the blocked contacts, without a folder, and
  says how many it kept.

Both deletes take `POST` or `DELETE` only.

## Alternatives

Changing `Invoice.matter` to `CASCADE` would have made the matter delete
simpler; the reason the key is `SET_NULL` is not recorded, and the fix
was kept to the view. Nothing records whether `Transaction.contact` was
considered for `PROTECT`; the blockers in Python name the reason to the
user and also cover the deposit requests and the client relationship,
which are not cascades.

## Consequences

- `deletion_blockers()` is the one place that says when a contact may
  not be deleted. A new record that hangs off a contact and must be kept
  needs a line there, not a new check in a view.
- A matter delete that bypasses the view (the Django admin, a shell)
  detaches the invoices again.
- The matter's `members` and `contacts` rows are through-table rows and
  go with the matter; the contacts themselves stay.

## Evidence

- `apps/matters/views.py`, `delete`, the comment: "The dialog counts the
  matter's invoices among what is deleted, and the database would only
  detach them (Invoice.matter is SET_NULL), leaving invoices with no
  matter, no entries and no payments."
- `Contact.deletion_blockers()` docstring in `apps/contacts/models.py`:
  "the database cascades to the client's trust ledger and trust deposit
  requests, and detaches the contact from the matters it is the client
  of. Those are records a firm has to keep, so the contact stays while
  they exist."
- Commit "fix(matters): closing dates, the practice-area filter, editing
  and deleting" (2026-10-02): "Deleting a matter left its invoices behind
  with no matter, though the dialog counts them among what is deleted.
  They are deleted with it."
- Commit "fix(contacts): deleting a contact or a folder cannot take a
  client's records with it" (2026-10-02), and "contacts: name trust
  deposit requests in the delete refusals" (2026-10-05).
- `Invoice.matter` in `apps/invoicing/invoices/models.py`;
  `Transaction.contact` in `apps/trust/models.py`.

## Related

- [Matters, contacts and parties](../dev/subsystems/matters.md): Deleting.
- [Trust and payments](../dev/subsystems/trust-and-payments.md).
- [The matter owns the client relationship](2026-07-02-the-matter-owns-the-client.md).
