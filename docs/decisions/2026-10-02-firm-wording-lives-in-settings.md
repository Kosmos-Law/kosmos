# Fee-agreement wording lives on the Firm record, not in templates (2026-10-02)

The invoice PDF prints the client's confirmed trust balance as a Retainer
Balance, and a footnote under it explained what the firm does with funds
in trust. The reminder emails for an invoice and for a payment request
stated the firm's payment terms. Both sentences were written into the
templates by the firm that built the application, and they described
that firm's fee agreement. With the repository public and the application
meant for other firms, every install was printing one firm's contract
language on another firm's invoices.

## Decision

Wording that depends on a firm's own fee agreement is a field on the
`Firm` record, not text in a template. The model comment: "Wording that
depends on a firm's own fee agreement. Blank leaves the sentence out of
the document." Two fields: `invoice_trust_note` (a `TextField`, the
footnote under Funds in Trust on the invoice PDF) and `payment_terms` (a
`CharField`, quoted by the invoice reminder and the operating payment
request reminder). Both are blank by default and "printed only when set";
they are edited under Settings, Firm, as Invoice Trust Note and Payment
Terms (migration settings 0009).

## Alternatives

- **Keep the wording in the templates.** The behaviour until 2026-10-02.
  It could not survive a second firm.
- **Ship a generic default sentence.** Not taken: the fields start blank,
  and the commit notes the cost, "A firm that relied on the old wording
  has to enter it once." The reason for blank over a neutral default is
  not recorded, though a trust note is contract language a firm should
  not inherit by accident.

## Consequences

- A new client-facing sentence that would vary by firm (a late-fee
  clause, a jurisdiction notice) belongs on `Firm` with the same shape:
  blank default, rendered only when set, edited on the Firm settings
  page. Do not put it in a template or a setting in `config/`.
- The templates guard on the field: the invoice PDF marks the Retainer
  Balance with an asterisk and prints the caption only when
  `company.invoice_trust_note` is set; the reminder emails print
  `payment_terms` only when it is non-empty. A template that references
  either must keep the guard, or an install with blank fields prints an
  empty footnote.
- The trust-request reminder does not use `payment_terms`; it uses
  "softer retainer language" of its own, because a deposit request is
  not an overdue debt.
- Upgrading an install that had the old wording is a one-time manual
  step: enter the firm's text under Settings, Firm.

## Evidence

- `apps/settings/models.py`, `Firm.invoice_trust_note` and
  `Firm.payment_terms` with their comment;
  `apps/settings/migrations/0009_firm_invoice_wording.py`.
- `templates/invoicing/invoices/invoice.html`, the Retainer Balance
  asterisk and `trust-caption`; `templates/emails/invoice_reminder_email.html`
  and `templates/emails/payment_request_reminder_email.html`, the
  `payment_terms` guard.
- `apps/invoicing/invoices/functions/send_invoice.py`, `send_reminder()`,
  and `apps/invoicing/requests/send.py`, `send_request_reminder()`, which
  read `company.payment_terms`.
- Commit: "fix(money): trust payments, payment edits, returned money and
  the figures that report them" (2026-10-02), the paragraph "The firm's
  own wording".

## Related

- [Time and billing](../dev/subsystems/time-and-billing.md), "The PDF"
  and "Sending and reminding".
- User guide: [Settings](../guide/settings.md).
