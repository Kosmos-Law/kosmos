# Trust and payments

Money coming in is a `Payment` applied to invoices; money held for a
client is a `Transaction` on the trust ledger; a client can pay either
one through a signed public link. The subsystem spans `apps/trust/` (the
ledger and the trust available figure), `apps/invoicing/payments/` and
`apps/invoicing/applications/` (payments and how they pay invoices),
`apps/invoicing/pay/` and `apps/invoicing/processors/` (online
collection) and `apps/invoicing/requests/` (payment and trust deposit
requests). Invoices, credits and the figures that report them are on
[Time and billing](time-and-billing.md).

Setup for a processor is in the operator guide:
[Online payments](../../admin/integrations/payments.md).

## Where the code is

| Path | What it holds |
|---|---|
| `apps/trust/models.py` | `Transaction`, one ledger row |
| `apps/trust/trust.py` | The balance functions: `calculate_balance()`, pending and confirmed balances, `get_clients_asymmetric()`, history |
| `apps/trust/available.py` | Trust available, "the single authority for the whole app" |
| `apps/trust/forms.py`, `apps/trust/views.py`, `apps/trust/get_trust_data.py` | The transaction form, the Summary, History and Client views, CSV export |
| `apps/invoicing/payments/` | `Payment`, `PaymentForm`, the Payments tab, applying to invoices |
| `apps/invoicing/payments/trust.py` | The payment-by-trust rule: `trust_balance()`, `sync_trust_withdrawal()`, `delete_trust_withdrawal()` |
| `apps/invoicing/applications/models.py` | `PaymentApplication`, `CreditApplication`, `apply_to_invoice()`, `delete_with_applications()` |
| `apps/invoicing/invoices/views.py` | `quick_invoice_payment()`, the Pay and Pay from Trust buttons on an invoice |
| `apps/invoicing/pay/` | The public pay pages (`views.py`), link builders (`links.py`), recording (`recording.py`, `balance.py`) and reconciliation (`reconcile.py`) |
| `apps/invoicing/processors/` | The processor contract (`base.py`), `factory.py`, and one adapter per processor |
| `apps/invoicing/requests/` | `PaymentRequest`, `PaymentRequestTransmission`, `send.py`, the Requests tab |
| `apps/invoicing/management/commands/` | `reconcile_pending`, `lawpay_accounts`, `confido_check` |
| `utils/signing.py`, `utils/ratelimit.py`, `utils/links.py` | Signed tokens, the public-page rate limiter, absolute URLs |
| `templates/invoicing/pay/pay.html`, `templates/invoicing/pay/unavailable.html` | The public pay page and its refusal page |
| `templates/trust/` | The Trust tab |

## Data model

### Transaction

`Transaction` (`apps/trust/models.py`, table `app_trust`) is a ledger row:
`contact` (the client, CASCADE), `date`, `type` (a plain `CharField`;
the form restricts it to `Deposit` or `Withdrawal`, and
`calculate_balance()` counts nothing else), `method` (`ACH`, `Card`,
`Wire`, `Transfer`, `Check`; blank on rows older than the field),
`description`, `amount` (`max_digits=9`), `entered`, `confirmed`, the
processor provenance fields (`processor`, `processor_txn_id`,
`processor_status`) and `payment`.

`payment` is a `OneToOneField` to `invoicing.Payment` with
`on_delete=SET_NULL`. The field comment is the reason it is not a
cascade: "The two are one movement of money: deleting the payment on its
own screen deletes its withdrawal. That is done there, on purpose, and
not by a cascade: a trust ledger row must never disappear as a side
effect (of deleting a whole matter, say)."

`fell_through` is a property: `processor_status` in `failed`, `returned`
or `voided`. The lists flag such a row; it exists because a deposit the
firm had already confirmed is kept on the ledger for staff to reconcile
by hand rather than deleted (see reconciliation below).

The contact side guards the cascade: `Contact.deletion_blockers()` in
`apps/contacts/models.py` refuses to delete a contact that "has trust
activity", because "those are records a firm has to keep".

### Payment

`Payment` (`apps/invoicing/payments/models.py`) has `matter` (CASCADE),
`date`, `amount`, `payment_method` from `PAYMENT_METHOD_CHOICES`
(`CHECK`, `CARD`, `ACH`, `TRUST`, `WIRE`), `detail`, and the same three
processor fields as a trust row, blank for a payment entered by hand.
`amount_unapplied` is `amount` less the sum of its applications.

A payment is tied to invoices through `PaymentApplication`
(`apps/invoicing/applications/models.py`): `payment` (CASCADE),
`invoice` (CASCADE), `amount_applied`, unique per (payment, invoice). Its
`save()` sets the invoice `PAID` when nothing remains; its `delete()`
calls `Invoice.reopen_if_no_longer_covered()`. The invoice-side rules
are on the billing page.

### PaymentRequest

`PaymentRequest` (`apps/invoicing/requests/models.py`) is "an outgoing
ask for money, paid via a tokenized link". `account` is `operating` or
`trust`; an operating request has a `matter`, a trust request a
`client`. `amount_requested`, `recipient_email`, `status` (`SENT`,
`PAID`, `CANCELED`) and a `uuid` for the token. Fulfilment is recorded on
`payment` (operating) or `trust_transaction` (trust), both SET_NULL.
`settlement_pending` reports a paid request whose fulfilling charge is
still `pending`. `PaymentRequestTransmission` mirrors
`InvoiceTransmission`: one row per email attempt, `kind` of `request` or
`reminder`.

## How it works

### The trust ledger

Every balance is `calculate_balance()` in `apps/trust/trust.py` over some
queryset: deposits add, withdrawals subtract. Two balances exist per
client and per account:

- **Pending** counts every row (`get_pending_client_balance()`,
  `get_pending_account_balance()`).
- **Confirmed** counts rows with `confirmed=True`
  (`get_confirmed_client_balance()`, `get_confirmed_account_balance()`).
  The confirmed balance is what the invoice PDF prints as the retainer
  balance.

`confirmed` is a hand flag on a manual row (`toggle_confirmed()` in the
views) and a bank flag on an online deposit (set when the processor
reports the funds deposited; see reconciliation).

The Summary view lists clients from `get_clients_asymmetric()`: every
contact with a ledger row whose asymmetric balance (all deposits, only
confirmed withdrawals), pending balance or confirmed balance is not zero.
The comment explains the three-way test: listing on the asymmetric
balance alone "hid a client whose pending or confirmed balance was still
non-zero, while the totals under the table, which add up every
transaction, went on counting them". `get_trust_data()` then attaches
the pending and confirmed balances and trust available to each row,
sorts by the session key `trust_order`, and paginates. The History view
(`history_index()`, `history()`) shows the account over 30 days, 60 days
or all time; the Client view shows one client's rows oldest first.

`history_csv()` downloads the whole ledger regardless of the on-screen
interval, oldest first, with withdrawals signed negative "so the Amount
column sums to the net account movement", for reconciliation against the
bank statement. It is the only reconciliation aid: there is no
reconciliation screen, and no action that marks a row as matched.

`TransactionForm` requires an amount above zero and a type of Deposit or
Withdrawal, and defaults a new row's method to Check. `edit()` and
`delete()` refuse a row with `payment_id` set and point the user at the
payment instead (`_belongs_to_a_payment()`); confirming such a row is
still allowed.

### Trust available

`apps/trust/available.py` holds the one formula, stated in its docstring:

```
trust_available(client) = PENDING trust balance
                        − currently owed across the client's non-deferred
                          invoices
                        − work in progress (net fees/expenses not yet
                          billed, drafts included) on the client's
                          non-deferred-fee matters
```

It is client-level because "a client's trust is one pooled balance that
ALL their matters draw on", and it uses the pending balance because
"firms customarily work against provisional deposits in the expectation
they'll clear". `_owed_by_client()` skips `DEFERRED` invoices and
reproduces `Invoice.amount_remaining`; `_unbilled_by_client()` skips
matters with `deferred_fees` and counts work on `DRAFT` and `APPROVED`
invoices net of those invoices' discounts. The entry points are
`trust_available_by_client()` (bulk), `client_trust_available()` (one
client; a matter passes `matter.client_id`) and
`attach_client_trust_available()` for Summary rows.
`trust_available_severity()` bands the figure: `danger` below zero,
`warning` under a quarter of the client's pending balance, `ok`, or
`none` when no trust is held.

Consumers: the Trust Summary, the Work in Progress tab, the matter ledger
and detail, the time-entry form, and the dashboard's low-trust watch
list (`dash_collections_context()`, which alarms below $1,000 and only
for clients who hold trust). The July 2026 refactor "one central,
client-level, pending trust-clearance calc" replaced per-screen copies of
this arithmetic; the figure was called "clearance" until the rename
to "trust available" on 2026-07-08.

### Recording a payment

`PaymentForm` (`apps/invoicing/payments/forms.py`) requires an amount
above zero and, on edit, refuses to shrink a payment below what is
applied or to move it off its matter (`_check_against_applications()`).
When the method is `TRUST` it also runs `_check_trust_funds()`: the
matter must have a client, and the amount may not exceed
`trust_balance()`, which is the client's pending balance excluding the
payment's own withdrawal so an edit is checked "against the balance as
it stood before the payment".

**The method decides.** `apps/invoicing/payments/trust.py` states the
rule: a payment whose method is Trust "always has one matching withdrawal
on the trust ledger, and a payment by any other method never has one".
Every view that saves a payment calls `sync_trust_withdrawal(payment)`
afterwards, inside the same `transaction.atomic()` block: it creates the
withdrawal, updates it (contact, date, amount, description follow the
payment), or deletes it when the method is no longer Trust. Deleting a
payment calls `delete_trust_withdrawal()` first, then
`delete_with_applications()`. The callers are `payments_add()`,
`payments_edit()`, `payments_delete()` and `quick_invoice_payment()`.
This module arrived on 2026-10-02 ("trust payments, payment edits,
returned money and the figures that report them"). Before it, only the
invoice's Pay from Trust button wrote a withdrawal, as an unlinked row
dated today, so a trust payment recorded on the Payments tab or edited
afterwards left the ledger wrong.

`quick_invoice_payment()` in `apps/invoicing/invoices/views.py` is the
Pay button on an invoice: the form starts at `invoice.amount_remaining`
("a second payment on a part-paid invoice starts at the remainder"),
pins the matter, presets the method to `TRUST` for the trust button, and
refuses the trust button on a matter with no client. On save it applies
`min(payment.amount, invoice.amount_remaining)` through
`apply_to_invoice()` and syncs the withdrawal; any excess stays
unapplied. `payments_apply()` is the general screen: it offers the
matter's `SENT` and `DEFERRED` invoices with a balance, validates every
amount before creating any, and rejects a total above
`amount_unapplied`. Removing an application
(`payments_delete_application()`) runs the model `delete()` and so
reopens the invoice.

### Online payments

**Links.** `apps/invoicing/pay/links.py` builds `/pay/<token>/` for an
invoice and `/pay/balance/<token>/` for a request. The token is
`django.core.signing` with a timestamp over the row's `uuid`, salted per
purpose (`utils/signing.py`): "an invoice token can't open a
matter-balance page or vice versa". Both are accepted for
`INVOICE_PAY_LINK_MAX_AGE` seconds (90 days by default) and then answer
`410`; a bad signature answers `404`. `utils/links.absolute()` uses the
request host, or `PUBLIC_BASE_URL` when there is no request.

**The pay page.** `pay_page()` in `apps/invoicing/pay/views.py` resolves
the invoice, refuses `VOID` and `UNCOLLECTIBLE` with `410`, asks the
active processor for a `ClientConfig` (publishable key, amount, methods,
hosted-fields URL), and renders `templates/invoicing/pay/pay.html` with
the amount due and a download link for the PDF. With the fake processor
the page renders a simulated-outcome form instead of hosted fields
(`dev_mode`). Card or bank details are tokenized in the browser by the
processor's own fields and never reach the server.

**The charge.** `pay_charge()` is `csrf_exempt` (no session) and
rate-limited by IP. It locks the invoice row with `select_for_update()`,
recomputes the amount from the locked row (not from `client_config()`,
which for Confido would mint and orphan a new session), refuses an
invoice with no matter, and returns "already paid" when nothing remains:
the lock plus that check is the double-charge guard. It passes the
browser's `card_type` (`credit` or `debit` from the hosted fields' BIN
lookup) through `metadata`, because Confido validates the completion
method against the card's real type. An accepted result (`SUCCEEDED` or
`PENDING`) is recorded by `record_payment()` in `recording.py`: one
`Payment` with the processor fields set, idempotent on
`processor_txn_id`, applied in full to the invoice so the usual hook
marks it `PAID`. A pending ACH charge is recorded the same way, so the
invoice shows paid provisionally; `Invoice.has_pending_payment` and the
list's `annotated_has_pending_payment` surface that. A result that is
neither raised nor accepted (a Confido "soft decline") is reported as
declined; this check was added on 2026-09-14 after such a charge had
been reported as success.

**Processors.** `get_processor()` in `processors/factory.py` reads
`PAYMENT_PROCESSOR` and returns one of:

| Name | Adapter | Notes |
|---|---|---|
| `fake` | `processors/fake.py` | The default; an in-process registry driven by token strings (`fake-ok`, `fake-decline`, `fake-soft-decline`, `fake-ach-return`, `fake-ach-fail`) with `simulate_settlement()`, `simulate_deposit()` and `simulate_event()` for tests. It records payments although no money moves |
| `none` | `processors/none.py` | Links still serve the documents; the page says to contact the firm; nothing can be charged. `online_payments_enabled()` is false, so invoice emails link "View invoice" instead of "Pay now", `send.py` refuses every request send, and the request actions are hidden. What a production install should run until a processor is configured |
| `lawpay` | `processors/lawpay.py` | AffiniPay REST; webhooks are unsigned and verified by re-fetching the transaction |
| `stripe` | `processors/stripe.py` | Single account, Stripe Elements, signed webhooks; cannot take trust deposits |
| `confido` | `processors/confido.py` | GraphQL; the server mints a payment session first (`client_config()` hits the API), the client submits to it, the server completes it; HMAC-SHA512 signed webhooks |

Every adapter maps its native states onto the statuses in
`processors/base.py`: `SUCCEEDED`, `PENDING`, `FAILED`, `RETURNED`,
`REFUNDED`, `VOIDED`. `ACCEPTED_STATUSES` (`SUCCEEDED`, `PENDING`) means a
payment may be recorded; `REVERSED_STATUSES` (`FAILED`, `RETURNED`,
`VOIDED`) means an accepted charge fell through. `ChargeResult.settled`
is separate from `SUCCEEDED`: it is the processor's "in the bank" state,
and it drives the trust `confirmed` flag.

**Operating versus trust, card versus bank.** The `charge()` call takes
`trust=True` for a deposit, and each adapter routes it:

- LawPay keeps four deposit accounts, discovered with
  `manage.py lawpay_accounts` and pinned in
  `LAWPAY_{OPERATING,TRUST}_{CARD,ECHECK}_ACCOUNT_ID`.
  `LawPayProcessor.account_id_for(method=, trust=)` picks one; a blank
  operating id lets the gateway choose its primary, a blank trust id is a
  `ProcessorConfigError`.
- Confido keeps two bank accounts, `CONFIDO_OPERATING_BANK_ACCOUNT_ID`
  and `CONFIDO_TRUST_BANK_ACCOUNT_ID`, both required; the account is
  baked into the payment session at `client_config_for()` time, so the
  `trust` flag on `charge()` is already reflected.
- Stripe pays into one account, so `trust_unavailable_reason()` returns
  a sentence and a trust request is refused before it is sent.

`PaymentProcessor.trust_unavailable_reason()` is the hook for that
refusal: `_trust_requests_unavailable()` in the requests views shows it
to staff, and `balance_pay_page()` refuses the page, so "trust money
must reach the trust account and nowhere else". eCheck is offered on the
pay form only when the adapter sets `ClientConfig.echeck`; the LawPay
adapter leaves it off because the firm's eCheck accounts were suspended,
though the bank charge path remains intact.

`online_payments_enabled()` in `processors/factory.py` is the one check
for "online payment is off" (the processor is `none`). Templates read it
as `online_payments_enabled` from the `config.context.payments` context
processor, which also offers `payment_requests_exist` (a callable, so the
query runs only where the Invoicing sub-nav asks) to keep the Requests tab
while older requests exist.

**Webhooks and reconciliation.** `processor_webhook()` at
`/webhooks/<processor>/` answers `200` at once and hands the raw body and
signature header to `reconcile_webhook()` through Django-Q `async_task`,
falling back to running it inline if the queue is unavailable. The
adapter's `verify_and_parse_webhook()` never trusts the body as posted:
LawPay re-fetches the transaction, Stripe verifies the signature, and
Confido verifies the signature and then re-fetches. `_apply_event()`
finds the `Payment` or `Transaction` carrying the transaction id (an
unknown id is a no-op) and:

- on a settle, updates `processor_status` (`_settle_or_reverse()`), and
  for a deposit also sets `confirmed=True` once `event.settled`
  (`_apply_to_deposit()`), "so the confirmed balance tracks the bank";
- on a reversal of a payment, `_reverse_payment()` deletes each
  application individually so the invoice reopens (the hook's
  `reopen_if_no_longer_covered()` handles the legacy Paid rule), deletes
  the payment, and emails the admins;
- on a reversal of a deposit, `_reverse_deposit()` deletes an unconfirmed
  deposit (its history row keeps the audit trail) but only flags a
  confirmed one, "don't silently mutate the confirmed ledger", and emails
  the admins;
- in both cases `_reopen_requests()` puts a `PAID` request fulfilled by
  that money back to `SENT`.

`poll_pending()` is the backstop for a webhook that never arrived: it
re-fetches every payment still `pending` and every online deposit still
pending or unconfirmed, and applies the result through
`_apply_event()`. It is the `reconcile_pending` command and the hourly
`payments-reconcile` schedule.

### Payment requests

An operating request (`requests_new()`) asks for a matter's open balance
or a firm-set amount up to it. The balance is `matter_balance_cents()`
in `pay/balance.py`: the sum of `amount_remaining` over the matter's
invoices outside `_NOT_PAYABLE` (`DRAFT`, `APPROVED`, `VOID`,
`UNCOLLECTIBLE`, `DEFERRED`). The request is saved and sent inside one
`transaction.atomic()` so a failed email leaves no request behind.

`send_payment_request()` in `requests/send.py` emails the link, never an
attachment; with `include_statement` or `include_invoices` it adds
tokenized download links for the matter ledger PDF and each open invoice
(`balance_statement_pdf()`, `balance_invoice_pdf()`, which refuse unsent
and void invoices and a cancelled request). Each linked invoice also gets
a `request`-kind `InvoiceTransmission`, so its send tally and
`days_since_sent()` reflect that the client was given it.
`send_request_reminder()` logs a `reminder` on the request and on those
invoices, quotes `days_since_requested()` and `Firm.payment_terms` for an
operating request, and uses "softer retainer language" for a trust one.
`requests_cancel()` moves `SENT` to `CANCELED`, which also revokes the
document links; `requests_resend()` sends the same link again.

Paying one is `balance_charge()`: it locks the request, charges
`request_charge_cents()` (an operating request is capped at the live
balance "so it can never overpay"; a trust request charges the firm-set
amount as-is), then records with `record_matter_balance_payment()`: one
`Payment` on the matter applied oldest-invoice-first across the open
invoices, each application flipping its invoice to `PAID` when covered.
A request found already settled, or with nothing left to charge while
still `SENT`, is marked `PAID` without a charge.

A trust deposit request (`requests_new_trust()`) is client-scoped: it
names a `Contact` from `active_or_pending_clients()`, not a matter, and
offers no statement or invoices. Paying it calls `record_trust_deposit()`
in `pay/balance.py`, which writes a `Deposit` row with `method` Card or
ACH and `confirmed=result.settled`, "normally False at charge time (a
card is merely captured, an ACH still in flight)". The request's
`trust_transaction` links the row.

The model and the request-based link were built in four commits on
2026-06-28 (`PaymentRequest` model, request-based catch-up link, the
Requests sub-tab, the request email with statement); the transmission
log and reminders followed on 2026-07-09, and the attachment-free email
with document links on 2026-07-10.

### What does not exist

- **No refund action.** `PaymentProcessor.refund()` is implemented by
  every adapter, but nothing in the application calls it; a refund is
  done in the processor's own portal, and the resulting webhook (status
  `refunded`) is not in `REVERSED_STATUSES`, so it only updates
  `processor_status`. Record the money movement by hand.
- **No reconciliation screen.** Reconciliation is the CSV export, the
  `fell_through` flag on the lists, and the admin emails from
  `reconcile.py`.
- **No matter-level trust.** Every trust figure is per client; a matter
  shows its client's.

## Background work

- `payments-reconcile`, hourly, runs `poll_pending()`; see the
  [schedules reference](../../reference/schedules.md). A row whose fetch
  fails is reported in the task result and tried again next hour.
- Webhook deliveries are queued with `async_task` from
  `processor_webhook()`; when queuing raises, the reconciliation runs in
  the request instead. A verification failure is logged and the delivery
  dropped (the processor retries on a non-200, but the view always
  returns 200, so an unverifiable delivery is gone; the hourly poll
  covers it).
- Reversals email the site admins with `mail_admins(fail_silently=True)`;
  nothing is retried if the email fails.

## Access

- `/invoicing/` (the Payments, Trust, Requests and Collection tabs, and
  the trust routes, which live under `/invoicing/trust/`) requires
  `perm_financial` or the admin role, enforced by `PermissionMiddleware`
  (`apps/accounts/middleware.py`). The views themselves are only
  `@login_required`. A contact page shows trust balances only to the same
  users (`can_see_trust()` in `apps/contacts/access.py`).
- `/pay/...` and `/webhooks/...` are public. The signed token is the only
  gate on a pay page; `rate_limited()` in `utils/ratelimit.py` throttles
  by IP (20 charges and 30 PDF downloads per 5 minutes, 240 webhook posts
  per minute) in the Django cache, which is per process under gunicorn,
  so the real limit is that times the worker count.
- `pay_charge()`, `balance_charge()` and `processor_webhook()` are
  `csrf_exempt`; a `POST` is required.

See the [permissions reference](../../reference/permissions.md).

## Things that bite

- **`Transaction.contact` cascades; `Payment.matter` cascades.** Deleting
  a matter deletes its payments, and because the ledger link is
  `SET_NULL` their trust withdrawals stay on the ledger, unlinked, with
  no payment to edit them through. The contact side is guarded by
  `deletion_blockers()`; the matter side is not.
- **`sync_trust_withdrawal()` must follow every payment save.** It is a
  convention, not a signal. A new code path that creates or edits a
  `Payment` with method `TRUST` and forgets the call leaves the ledger
  short.
- **Online rows are matched by `(processor, processor_txn_id)`.** Both
  `record_payment()` and `record_trust_deposit()` are idempotent on that
  pair, and `_apply_event()` routes by it. A test that reuses a
  transaction id across the fake registry's lifetime will find the
  earlier row.
- **`PENDING` is recorded as paid.** An ACH charge marks the invoice
  `PAID` the moment it is accepted. `processor_status` is the only sign
  it is provisional; a report that counts `PAID` invoices counts it.
- **A reversed deposit that was confirmed is not deleted.** It stays on
  the ledger with `fell_through` true and still counts in every balance
  until someone edits it. The pending and confirmed balances are wrong
  until then, by design.
- **The pay page's `client_config()` has side effects on Confido.** It
  mints a payment session on every render. Never call it from the charge
  path, and expect orphaned sessions from page reloads.
- **Rate limits reset on restart and are per worker.** The limiter's
  docstring says so; do not treat the numbers as a security control.

## Related

- User guide: [Payments](../../guide/payments.md),
  [Trust](../../guide/trust.md), [Invoicing](../../guide/invoicing.md),
  [Settings](../../guide/settings.md).
- Operator guide: [Online payments](../../admin/integrations/payments.md)
  for processor keys, account ids, webhook URLs and the go-live checks.
- [Time and billing](time-and-billing.md) for invoices, credits, the
  amount-remaining rule and the reports; [Matters](matters.md) for
  `Matter` and `Contact`; [Operations](operations.md) for the worker the
  reconciliation runs on.
