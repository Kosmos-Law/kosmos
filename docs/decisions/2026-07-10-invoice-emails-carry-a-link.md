# Invoice emails carry a link, and the stored PDF is what the link serves (2026-07-10)

The billing emails (invoice, reminder, payment request and its reminder)
began life attaching a PDF. A money request with a PDF from a low-volume
sender is the classic phishing shape, and in July 2026 one such request
was quarantined by a recipient's mail filter. At the same time the public
pay page already existed, behind a signed token, and could serve the
documents itself. A second question followed from the first: once the
link serves a stored file, which copy of the invoice is the client
looking at, and when is it remade?

## Decision

Billing email carries no attachment by default. The invoice and reminder
emails have an "Attach invoice PDF" box, off by default, whose copy
adapts; payment requests never attach and instead offer "Include
statement link" and "Include invoice links". `send_invoice()` states the
reason in its docstring: "the PDF is always downloadable behind the
tokenized pay link, and attachment-free email clears spam filters more
reliably". A download link counts as a delivery: each linked invoice gets
a `request`-kind transmission row, so the send tally and
`days_since_sent()` reflect it.

The stored PDF is the client's copy, and it is remade at the moments the
client's view of the invoice changes: on create and edit, when the status
moves to Approved or Sent, when the invoice leaves Draft by any other
road, when a send issues it (rendered as Sent before the email goes), and
on void (stamped Void, before the entries are released). A move between
later statuses (Sent to Deferred, say) "leaves the copy the client was
sent". A resend keeps the copy the client has. A Draft is never served
from storage; `invoices_pdf()` renders it fresh.

## Alternatives

- **Attach by default.** The original behaviour, from June 2026 to
  2026-07-10, retired for the reason above. The option survives as the
  off-by-default box.
- **Hot-link the firm logo instead of embedding it.** Rejected in the
  same commit: "media URLs are signed and expire, so hot-linking would
  break archived email". The logo is CID-embedded.
- **Regenerate on every status change.** This was the behaviour until
  2026-10-02 and was a bug: Sent to Deferred "replaced the copy the
  client's link serves with one carrying that day's trust balance".
- **Store only when no copy exists.** Voiding did this until 2026-10-05,
  so no stored copy ever carried the void stamp.

## Consequences

- The pay link is the document channel. Its token (`utils/signing.py`,
  salted per purpose) is accepted for `INVOICE_PAY_LINK_MAX_AGE`, 90 days
  by default; a client past that sees 410 and needs a resend.
- Voiding an invoice or cancelling a request revokes its public
  documents; paid records keep read-only access as a courtesy.
- Editing a draft's or an approved invoice's entries does not remake the
  stored PDF; the next status move does. An Approved invoice whose
  entries change keeps the stale copy until it is moved or sent.
- The public pay page regenerates when `pdf_file` is empty or the file is
  missing from storage, after a storage move once lost the files.
- The `generate_invoice_pdfs` command stores a PDF for every invoice
  without one, for installs that predate storage.

## Evidence

- `apps/invoicing/invoices/functions/send_invoice.py`, the `attach_pdf`
  paragraph of `send_invoice()` and `_store_pdf_as_sent()`: "Store the
  PDF as the client will see it: the watermark follows the status at
  render time".
- `apps/invoicing/invoices/views.py`, `invoices_edit_status()`: "the copy
  kept from the draft carries the DRAFT watermark, and it is what the
  client's link serves"; `invoices_void()`: "a copy made after that would
  be a blank page".
- `apps/invoicing/requests/send.py`, `send_payment_request()`.
- Commits: "feat(pay): tokenized document downloads on the pay pages;
  firm logo" and "feat(invoicing): attachment-free billing email;
  document links; firm logo" (both 2026-07-10); "fix(money): a payment's
  trust withdrawal is changed only through the payment; credits get the
  payment's edit checks" (2026-10-02, the PDF paragraph);
  "fix(invoicing): remake the stored PDF when a send issues an invoice
  and on void" (2026-10-05).

## Related

- [Time and billing](../dev/subsystems/time-and-billing.md), "The PDF"
  and "Sending and reminding".
- [Trust and payments](../dev/subsystems/trust-and-payments.md), "Online
  payments" and "Payment requests".
