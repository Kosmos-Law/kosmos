# Time and billing

Time, expense and flat-fee entries accrue against matters; invoices gather
them up and turn them into receivables; credits and payment applications
pay those receivables down; the reports read the same rows back as
activity, revenue, realization, work in progress and aging. The subsystem
spans `apps/activity/` (the entries), `apps/invoicing/` (invoices,
credits, applications and the Work in Progress tab), `apps/reports/`,
and the `Matter.value` property in `apps/matters/models.py` that the
matter detail, the ledger and the invoice form all read.

The money that comes in, and the trust ledger, are on
[Trust and payments](trust-and-payments.md).

## Where the code is

| Path | What it holds |
|---|---|
| `apps/activity/time/`, `apps/activity/expenses/`, `apps/activity/flat_fees/` | One package per entry type: model, form, filter, list data builder, summary, CSV export, views |
| `apps/activity/models.py` | `ActivityCategory`, the per-matter coding buckets |
| `apps/activity/categories/views.py` | `set_category()`, the one endpoint that files an entry under a category |
| `apps/activity/access.py` | Who may reach an entry, which matters a form offers, and the invoice lock |
| `apps/activity/presets.py`, `apps/activity/chips.py` | Date presets and user-chip pinning shared by the three Activity tabs |
| `apps/invoicing/invoices/` | `Invoice` and `InvoiceTransmission`, the list annotations, status moves, PDF and email |
| `apps/invoicing/invoices/functions/` | `generate_invoice.py` (WeasyPrint), `send_invoice.py`, `generate_ledes_98b.py` |
| `apps/invoicing/credits/`, `apps/invoicing/applications/` | `Credit`, and the `PaymentApplication` / `CreditApplication` rows that pay an invoice |
| `apps/invoicing/unbilled/` | The Work in Progress tab and bulk invoice creation |
| `apps/invoicing/collection/` | The Collection tab (balances due by matter) |
| `apps/matters/models.py` | `Matter.value`: the matter's totals, unbilled, drafted, work in progress and billed figures |
| `apps/matters/rates/` | `Rate`, a per-user rate on one matter |
| `apps/matters/categories/`, `apps/matters/activity/` | Category management and the matter's Activity tab, including the Fee and Expense Report |
| `apps/reports/` | One package per report; each has an `aggregation.py` (or builds its rows in `views.py`) |
| `apps/dash/views.py` | `dash_wip_context()`, the dashboard's Unbilled Time section |
| `templates/invoicing/invoices/invoice.html` | The invoice PDF template |
| `templates/emails/invoice_email.*`, `templates/emails/invoice_reminder_email.*` | The invoice and reminder emails |

## Data model

### Entries

`TimeEntry` (`apps/activity/time/models.py`), `ExpenseEntry`
(`apps/activity/expenses/models.py`) and `FlatFeeEntry`
(`apps/activity/flat_fees/models.py`) share a shape: `date`, `matter`
(CASCADE), `user` (SET_NULL), an amount, `comp`, `entered`, and an
`invoice` foreign key with `on_delete=SET_NULL`. All three carry
`simple_history`.

- **Amounts.** A time entry's fee is `hours * rate`, computed where it is
  read (the `fee` property, or `F("hours") * F("rate")` in a query); it is
  never stored. `hours` is `DecimalField(max_digits=3, decimal_places=1)`,
  which is the one-decimal rule and a ceiling of 99.9 hours on one entry.
  `rate` is an `IntegerField` of whole dollars. An expense `amount` is
  `DecimalField(max_digits=6, decimal_places=2)`, so one expense tops out
  at $9,999.99; a flat fee allows `max_digits=10`. These limits are
  database columns, not form checks: the form reports them as validation
  errors because Django's `DecimalField` validates digits.
- **`comp`** marks work written off: it stays on the invoice (printed
  with a `comp` class and a "less comp" line when `Invoice.show_comp` is
  on, left out of the PDF when it is off) and is subtracted from every
  net figure.
- **`entered`** marks an entry billed outside Kosmos. Everything that
  gathers unbilled work (`Invoice.save()`, the Work in Progress tab,
  `Matter.value["unbilled"]`, the WIP and realization reports) excludes
  `entered=True`, and an entered entry is never picked up by an invoice.
  The realization report's comment states the reason: "Time marked
  Entered was billed outside Kosmos: it is not work in progress, and
  Kosmos cannot say what became of it."
- **`locked`** is a property, not a column: an entry is locked when its
  invoice has left `DRAFT`. The lists stop linking to a locked entry, and
  `locked_response()` in `access.py` refuses the edit or delete request
  itself. Setting a category stays allowed on a locked entry because it
  never touches an invoiced amount (`set_category()` says so).
- **Category.** `TimeEntry.category` and `ExpenseEntry.activity_category`
  point at an `ActivityCategory` with SET_NULL; flat fees have none. The
  expense field is named differently because `ExpenseEntry.category` is
  the free-text descriptor printed on invoices (Filing Fee, Postage and so
  on, from `ExpenseEntryForm.CATEGORY_CHOICES`).

`ActivityCategory` (`apps/activity/models.py`) belongs to one matter, is
unique per matter by name (`uniq_category_name_per_matter`), carries
`claimed` and a drag-set `position`. Its docstring is the design: "like
accounting transaction codes, each entry lives in exactly one category (or
none)", and claimed categories become the sections of the matter's Fee
Claim Report. `apps/activity/categories/views.py` adds that because an
entry has at most one category, "assignment is a plain dropdown, not a
label-style apply modal, and no double-counting guards are needed
anywhere". The badge-and-colour column it started with was replaced by
the folder-style column in July 2026 ("folder-style category column;
drop badges and colors").

`AbbreviationCode` (`apps/activity/time/models.py`) is a firm-wide
`code` → `expansion` pair with `is_active`. Codes are case-sensitive and
keep their spaces; the form sets `strip = False` on both fields because
"a code's own spaces are how it marks a word's edge".

`Rate` (`apps/matters/rates/models.py`) is a user's rate on one matter.
`calculate_rate_for_matter()` in `apps/activity/time/views.py` prefers it
and falls back to `CustomUser.user_rate`.

On `Matter` the billing fields are `billable` (non-billable matters are
internal work and are excluded from the Work in Progress tab and the
reports), `billing_type` (`HOURLY` or `FLAT_FEE`), `flat_fee_amount`, and
`deferred_fees`, whose comment reads: "fees accrue but are not currently
collectible, and the retainer is waived". That flag is read by trust
available and the dashboard's low-trust watch list, not by invoicing.

### Invoices

`Invoice` (`apps/invoicing/invoices/models.py`) has `matter` (SET_NULL),
`date_limit` (entries dated on or before it are gathered), `date_issued`,
`message` (the client-facing cover note), `comment` (internal),
`show_comp`, `discount`, `status`, `pdf_file`, `date_sent` and a `uuid`.
The `uuid` exists for the public pay link: the comment says "never expose
the sequential pk publicly. Rotating it invalidates outstanding links."

The statuses are `DRAFT`, `APPROVED`, `SENT`, `DEFERRED`, `PAID`,
`UNCOLLECTIBLE` and `VOID`. `UNSENT_STATUSES = ("DRAFT", "APPROVED")` is
the set every other module imports when it needs "assembled but not yet
issued"; the comment beside it is the rule: "Work on these invoices is
still work in progress, not a receivable: it stays out of the ledger and
balance due."

`InvoiceTransmission` is one row per email attempt (`kind` of `invoice`,
`reminder` or `request`; `status` of `sent` or `failed`; the addresses,
the sender, the error). `Invoice.date_sent` mirrors the latest successful
send of the invoice itself.

### Credits and applications

`Credit` (`apps/invoicing/credits/models.py`) is money the firm forgives on
a matter: `matter` (CASCADE), `date`, `amount`, `detail`. A `Payment` is
money received; it is described on the trust and payments page. Both are
tied to invoices through an application row in
`apps/invoicing/applications/models.py`: `PaymentApplication` and
`CreditApplication`, each with `invoice` (CASCADE), `amount_applied`
(`MinValueValidator(0.01)`) and a `UniqueConstraint` on (source, invoice),
so one payment or credit has at most one application per invoice.

## How it works

### Recording an entry

Each entry type has an add view, an edit view and a delete view in its
package's `views.py`, all `@login_required`, all reached by HTMX and
answering `204` with an `HX-Trigger` (`timeChanged`, `expensesChanged`,
`flatFeesChanged`) that re-renders the list.

- **Which matters the form offers** comes from
  `matters_for_entry_form()` in `apps/activity/access.py`: matters in
  `ENTRY_FORM_STATUSES = ("Pending", "Open", "Complete")`, narrowed by
  `billing_type` and by what the user may see
  (`filter_matters_for_user()` in `apps/accounts/access.py`), plus one
  `include_id` so a closed matter stays selectable on the form opened from
  it or on the entry already on it. `TimeEntryForm.clean_matter()` refuses
  a non-hourly matter and `FlatFeeEntryForm.clean_matter()` a non-flat-fee
  one; expenses go on either.
- **The rate** is filled client-side from `set_rate()` when the matter
  changes, and the same view shows the client's trust available beside it
  (`trust_available()`, which calls `client_trust_available()` from
  `apps/trust/available.py`).
- **Abbreviations** expand on save, on add and on edit alike, when the
  form's `apply_codes` box is ticked (it is by default).
  `_apply_abbreviation_codes()` runs plain `str.replace` over the text in
  the order `abbreviation_codes_in_order()` returns: longest code first,
  ties alphabetical, "so a code that is a substring of another" cannot
  pre-empt the longer match. The `codes/json` endpoint serves the same
  order to the browser preview so preview and saved text agree.
- **Moving an entry** between matters clears its `invoice`: a draft
  invoice belongs to the matter the entry left. The bulk matter move and
  the bulk comp change (`time_bulk_update_matter()`,
  `time_bulk_update_comp()`) skip locked entries and say how many they
  skipped in a toast.
- **The list** is built by `get_time_data()` (and its expense and flat-fee
  twins) from the session filter `time_filter`, re-deriving date presets
  from today on every read (`refresh_date_preset()`; see the
  [session state conventions](../conventions/session-state.md)). The user
  stepper on the toolbar and the `[` / `]` shortcut call
  `cycle_user_filter()` in `apps/management/user_filter.py`, which walks
  the active users in username order, wrapping, with no "All users" stop:
  from All Users the cycle enters at the first or last user. The pinned
  user chips are the same set the tasks tab uses
  (`CustomUser.task_user_chips`, capped at `TASK_CHIPS_CAP`).

### Categories

Category management (add, edit, delete, reorder, toggle claimed) is on the
matter's Categories tab in `apps/matters/categories/views.py`. Filing an
entry is `set_category()` in `apps/activity/categories/views.py`, which
looks the category up scoped to the entry's own matter "so a foreign
category can't be set". The matter's Activity tab
(`apps/matters/activity/views.py`) groups by category, honours
`Matter.uncategorized_claimed`, and renders the Fee and Expense Report
from the `report_*` options stored on the matter.

### Building an invoice

An invoice gathers its entries in `Invoice.save()`: while the status is
`DRAFT`, every time, expense and flat-fee entry on the matter dated on or
before `date_limit`, on no invoice and not `entered`, is pointed at it.
This runs on every save of a draft, so editing a draft's dates
(`invoices_edit()`, allowed only in `UNSENT_STATUSES`) re-sweeps the
matter. Nothing is copied: the entry's `invoice` foreign key is the
whole relationship, and the invoice's amounts are always computed from
the entries that point at it.

Invoices are created from `invoices_add()` (the form offers only matters
with unbilled work on a billable matter, each labelled with its
`Matter.value["unbilled"]` total) or in bulk from the Work in Progress
tab (`unbilled_bulk_create_invoices()`). `invoices_add()` stores the PDF
at once; the bulk path does not, and relies on the later status change or
the on-demand generation described below.

### Amounts

Three places compute an invoice's figures, and they must agree:

- `Invoice.value` (one invoice, Python): gross, comp and net for fees,
  expenses and flat fees, `pre_discount_total` and `final_total`.
- `Invoice.amount_remaining`: `final_total` less payment and credit
  applications, with two overrides. `VOID` and `UNCOLLECTIBLE` return 0
  ("nothing collectible"). A `PAID` invoice with no applications at all
  returns 0: invoices from before applications existed look like that.
- `get_annotated_invoice_queryset()` in `get_invoice_data.py` is the same
  arithmetic as database annotations (`annotated_final_total`,
  `annotated_amount_remaining`, `annotated_has_pending_payment`,
  `annotated_send_count`) for the list, and `get_invoice_data()` sums
  `total_amount_due` from them with the same two overrides.

`_owed_by_client()` in `apps/trust/available.py` reproduces the rule a
fourth time, in bulk, and says so in its docstring. Change the rule in
`amount_remaining` and the other three copies by hand.

### Status moves

The status menu posts to `invoices_edit_status()`. It accepts only
`SETTABLE_STATUSES = ("DRAFT", "APPROVED", "SENT", "DEFERRED",
"UNCOLLECTIBLE")`: the comment above it explains that Paid is set by
applying payments and Void by its own action, so neither is offered. A
`VOID` invoice cannot be moved at all. An invoice with `date_sent` set
(one actually emailed) cannot go back to `APPROVED` or `DRAFT`; a `SENT`
set by hand and never emailed still can.

The PDF is stored on the way to `APPROVED` or `SENT`, and on any other
move out of `DRAFT`, because "the copy kept from the draft carries the
DRAFT watermark, and it is what the client's link serves". A move between
later statuses (Sent to Deferred, say) leaves the copy the client was
sent.

`PAID` is set by `PaymentApplication.save()` and `CreditApplication.save()`
when `amount_remaining` reaches 0, and unset by their `delete()` through
`Invoice.reopen_if_no_longer_covered()`, which returns a Paid invoice to
the status it was paid from (`status_before_paid`: the latest non-Paid
row of its history when that is `SENT` or `DEFERRED`, else `SENT`) when
it has no allocations left or a balance again. Its docstring
explains why `amount_remaining` alone cannot decide: the legacy rule would
keep an invoice Paid after its last allocation was removed.

Deleting (`invoices_delete()`) is allowed for `DRAFT` and `APPROVED`, and
for `VOID` by an admin; anything else is 403.

### The PDF

`generate_invoice()` in `functions/generate_invoice.py` renders
`templates/invoicing/invoices/invoice.html` with WeasyPrint. The context
carries the entries (comped ones only when `show_comp`), the `Firm`
record (name, address, logo), and the client's **confirmed** trust balance
from `get_confirmed_client_balance()`, printed as Retainer Balance when
above zero with `Firm.invoice_trust_note` as its footnote. The caller
passes either the request or a `base_url`; `_static_file_url_fetcher()`
resolves static and media paths from the filesystem when the base URL is
a `file://` one, which is how the `generate_invoice_pdfs` management
command runs without a request.

`store_invoice_pdf()` generates, deletes the previous file and saves the
new one as `invoices/<matter_id>/<pk>.pdf` (`invoice_upload_path()`). It
is called on create, on edit, on the status moves above, by a send that
issues the invoice (one out of `DRAFT` or `APPROVED`, rendered as `SENT`
before the email goes), and on void (rendered stamped Void, before the
entries are released). `invoices_pdf()` serves the
stored file except for a `DRAFT`, which is always rendered fresh (with
the DRAFT notation in the filename). The public pay page's
`_invoice_pdf_response()` regenerates when the field is empty or the file
is gone from storage, after a storage move once lost the files while
every `pdf_file` field kept pointing at them.

### Sending and reminding

`send_invoice()` in `functions/send_invoice.py` emails the client. The
recipient defaults to the matter client's email; addresses are validated
with `validate_email`; the `From`, `Reply-To` and BCC come from the
`Firm` record through `utils/mail.py` (`billing_from_email()`,
`billing_reply_to()`, `Firm.invoice_bcc`). The PDF is not attached unless
asked: the email carries a pay link, `payment_url()` from
`apps/invoicing/pay/links.py`, a `TimestampSigner` token over the invoice
`uuid` (`utils/signing.py`) that the pay views accept for
`INVOICE_PAY_LINK_MAX_AGE` (90 days by default; see the
[environment reference](../../reference/environment.md)), and the PDF is
downloadable behind that link. A send out of `DRAFT` or `APPROVED`
remakes the stored PDF first (`_store_pdf_as_sent()`); a resend keeps
the copy the client has. On success the invoice becomes `SENT` with
`date_sent` and a `sent` transmission row; on any failure a `failed` row
is written, `InvoiceSendError` is raised and the status is left alone.

`send_reminder()` emails a payment reminder for a sent invoice: it quotes
`days_since_sent()` (days since the invoice itself, or a payment request
that attached it, was delivered; reminders do not reset the clock) and
`Firm.payment_terms` when set, logs a `reminder` transmission, and
changes nothing on the invoice. The list's `×N` chip counts every
successful transmission, invoices and reminders alike. The list offers
Send on `APPROVED` rows and Resend or Remind on `SENT` rows that have a
`date_sent` (`templates/invoicing/invoices/row.html`).

### Voiding

`Invoice.void()` releases every entry back to unbilled (`invoice=None`),
deletes the invoice's payment and credit applications, and sets `VOID`.
The applications' `delete()` hooks do not run (it is a queryset delete),
which is fine here because the invoice is leaving the receivable statuses
anyway. The released entries reappear on the Work in Progress tab and are
picked up by the next draft. The public pay link and PDF link answer
`410` for a void invoice. A `DRAFT` or `APPROVED` invoice cannot be
voided (delete it instead).

### Applying credits and payments

`apply_to_invoice()` in `apps/invoicing/applications/models.py` is the
one function every path uses to record an amount against an invoice. It
adds to the existing application for that (source, invoice) pair when
there is one, because the unique constraint would refuse a second row.
`delete_with_applications()` is the one way to delete a payment or credit
that has applications: it deletes each application individually first, so
the `delete()` hook runs and the invoice reopens; a cascade would skip
the hook and leave the invoice Paid.

`credits_apply()` and `payments_apply()` offer the source's own matter's
`SENT` and `DEFERRED` invoices with a balance, validate every amount
before creating any, and refuse a total above the source's unapplied
amount. `CreditsForm.clean()` and `PaymentForm.clean()` both refuse to
shrink a source below what is applied or to move it to another matter.

### Work in progress

`get_unbilled_data()` in `apps/invoicing/unbilled/unbilled.py` lists the
billable matters with any time, expense or flat fee that is on no invoice
and not entered, with per-matter subqueries (not joins, to avoid
multiplication), an optional activity-period cutoff, and the last invoice
date. The trust columns come from the trust app: the pending balance per
client and `trust_available_by_client()`. The total trust at the foot is
counted once per client (`clients_counted`), "Trust belongs to the client,
not the matter". Selecting matters and pressing the bulk action creates
one draft per matter with the dates given.

### Retainer plans

There is no retainer plan code in this repository: no app, model, field
or migration for a client-level flat fee, an included-hours pool or
anything named "retainer plan". The only billing arrangement is per
matter, through `Matter.billing_type`, `Matter.flat_fee_amount` and
`Matter.deferred_fees`, and a flat-fee matter bills by `FlatFeeEntry`
rows. The word "retainer" appears only as the trust balance printed on an
invoice and in trust-request wording.

### Reports

Each report has a session-held window and a `period` view that steps it.
What each one counts, from the module docstrings:

| Report | Source rows | Counts |
|---|---|---|
| Activity (`apps/reports/activity/`) | `TimeEntry` on billable matters, by entry date | Hours and fees per user per month over a 6-month window |
| Revenue (`apps/reports/revenue/`) | `Payment` by payment date, followed through its applications | Cash per month attributed to the users whose billable hours it covered; expense, flat-fee, unassigned and unapplied cash in trailing buckets; each month reconciles to the sum of `Payment.amount` |
| Realization (`apps/reports/realization/`) | `TimeEntry` on billable matters, by entry date; flat fees as a separate band | Each accrued fee dollar lands in exactly one of Collected, Credits applied, Outstanding, Deferred, Uncollectible, Write-downs, Unbilled (WIP) or Flat fees; the rate is Collected over hourly fees; the latest selectable month is the previous complete one |
| Work in Progress (`apps/reports/wip/`) | `TimeEntry` only: no invoice, not entered, billable matter | A snapshot of unbilled time by user and by matter; no date window on the report page |
| Clients (`apps/reports/clients/`) | Contacts that are the primary client of a matter | Hours, fees, billings and payments, lifetime by default |
| AR Aging (`apps/reports/aging/views.py`) | `SENT` invoices with `amount_remaining > 0` | Buckets by days since `date_issued`: 0 to 30, 31 to 60, 61 to 90, 91 to 120, over 120 |
| Intakes (`apps/reports/intakes/`) | `Intake` rows by month | Volume, practice area and outcome over 6 months |

Three figures are all called work in progress, and they differ on purpose:

1. **The dashboard and the WIP report** use `_wip_base()` in
   `apps/reports/wip/aggregation.py`: time only, on no invoice, not
   entered, billable matters. The dashboard defaults its period to "this
   month" (`dash_wip_context()`), so it is this month's unbilled time, not
   the firm's total exposure.
2. **The Work in Progress tab and the invoice form** use the invoicing
   queue: time, expenses and flat fees on no invoice and not entered. This
   is `Matter.value["unbilled"]`, whose comment reads: "Unbilled fees and
   expenses (entered=False, no invoice): the invoicing queue. Not the whole
   of work in progress; see drafted below."
3. **The ledger, trust available and realization** count drafts too.
   `Matter.value["work_in_progress"]` is "everything not yet billed: the
   invoicing queue plus the drafts, net of the discounts already set on
   those drafts"; `Matter.value["drafted"]` is "entries on invoices not yet
   issued (DRAFT/APPROVED). Off the invoicing queue, but still work in
   progress until the invoice is sent." The realization report puts the
   fees on an unsent invoice in its Unbilled (WIP) segment for the same
   reason, and `_unbilled_by_client()` in `apps/trust/available.py` does
   the same so a matter's trust available does not jump while a draft is
   open.

The change that made drafts count as work in progress landed on
2026-10-02 ("ledger: count work on draft invoices as work in progress");
before it, drafting an invoice made the work disappear from the ledger
until the invoice was sent.

## Background work

Nothing here runs on a schedule. PDF generation and email are synchronous
in the request. The `generate_invoice_pdfs` command stores a PDF for every
invoice that lacks one (see the
[commands reference](../../reference/commands.md)). The hourly
`payments-reconcile` job belongs to the payments page.

## Access

- Everything under `/invoicing/` and `/reports/` is gated by
  `PermissionMiddleware` in `apps/accounts/middleware.py`: `/invoicing/`
  needs `perm_financial`, `/reports/` needs `perm_reports`, and an admin
  passes both. The matter's `rates` and `ledger` pages are gated by
  pattern to `perm_financial`. The matrix is in the
  [permissions reference](../../reference/permissions.md).
- The Activity tabs are open to every signed-in user, but
  `entries_for_user()` and `entry_for_user()` in `apps/activity/access.py`
  limit a user without `perm_all_matters` to entries on their assigned
  matters, and the CSV exports go through the same filter. Bulk matter
  moves and bulk comp changes additionally require `perm_financial` (the
  check is in each view).
- The dashboard's by-user and by-matter WIP breakdown is shown to admins
  and `perm_reports` users; everyone else sees only their own unbilled
  time (`dash_wip_context()`).
- A matter detail's financial tabs are hidden and refused for users
  without `perm_financial` (`apps/matters/views.py`).

## Things that bite

- **`Invoice.save()` sweeps the matter on every draft save.** Any code
  that saves a `DRAFT` invoice, for any field and with or without
  `update_fields`, re-attaches every eligible entry up to `date_limit`.
  Use a queryset `update()` when a draft must be touched without that.
- **Four copies of the amount-remaining rule.** `Invoice.amount_remaining`,
  `get_annotated_invoice_queryset()`, `get_invoice_data()`'s total and
  `_owed_by_client()` in the trust app each special-case `VOID`,
  `UNCOLLECTIBLE` and the legacy Paid-without-allocations invoice. The
  realization report's `_invoice_facts()` has the legacy Paid rule as
  well.
- **`entered` means "billed elsewhere", not "entered into Kosmos".** It
  hides an entry from every unbilled and WIP figure and from the
  realization report, with no reversal path once the entry is also on no
  invoice. The toggle for it on the amount lists was removed on
  2026-10-02 ("Remove the Entered toggle on amounts"); it is still a field
  on each entry form.
- **The lock is on the entry, not the invoice.** `locked` is a property
  read through `entry.invoice.status`, so an entry list needs
  `select_related("invoice")` or it costs a query per row, and a bulk
  `update()` bypasses the lock entirely.
- **PDF regeneration is not automatic after edits to entries.** Editing a
  comp flag or an amount on a draft's entry does not regenerate the stored
  PDF; the next status move does, and `invoices_pdf()` renders a draft
  fresh anyway. An `APPROVED` invoice whose entries change keeps the stale
  stored copy until it is moved or sent.
- **`Matter.value["invoices"]` has no balance due.** It carries `billed`
  and `payment_sum` only; the ledger computes what is owed from the
  applications (`get_ledger_data()`), and so should anything else.
- **Date presets are rebuilt on read.** The Activity filter stores
  `filter_label`, and `refresh_date_preset()` recomputes `date_min` and
  `date_max` from today on every list render, so a stored window is not
  the window that will be shown.
- **The WIP report asserts in DEBUG.** `build_wip_context()` and
  `build_realization_context()` carry `assert` reconciliations that run
  only with `DEBUG=True`; a change that unbalances a report fails in
  development and silently misreports in production.

## Related

- User guide: [Time and expenses](../../guide/time-and-expenses.md),
  [Invoicing](../../guide/invoicing.md), [Reports](../../guide/reports.md),
  [Settings](../../guide/settings.md) (the firm's billing email, payment
  terms and trust note).
- [Trust and payments](trust-and-payments.md): payments, applications
  from the money side, the trust ledger and online collection.
- [Matters](matters.md) for `Matter`, membership and the practice shell;
  [Session state](../conventions/session-state.md) for the filters and
  selections the lists use.
