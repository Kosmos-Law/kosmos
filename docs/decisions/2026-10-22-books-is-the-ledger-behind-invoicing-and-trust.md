# Books is the ledger behind invoicing and trust (2026-10-22)

The owner wanted the firm's accounting in Kosmos: what QuickBooks does
for a law practice, without QuickBooks. Two projects already held most
of the pieces. Kosmos had invoices, payments, credits, the trust ledger,
expense entries, processor reconciliation and the billing reports. A
separate personal-finance project held bank feeds (Plaid and CSV
import), payee rules, transfer matching and period reports. Neither had
a general ledger: Kosmos's trust ledger is one table of deposits and
withdrawals, and the finance project's chart of accounts is single-entry
categorisation.

## Decision

Books is a module of Kosmos, `apps/books`, not a third application and
not a separate shell. It is a double-entry general ledger: a chart of
accounts and journal entries whose debits equal their credits, with the
statements computed from the lines.

- **The practice apps stay the records staff work in.** Invoicing, trust
  and the expense entries are not moved or changed. Books listens to
  them: an event there (a payment lands, trust money moves, a cost is
  advanced) posts a journal entry here. Posting is one-way and in-repo;
  the practice apps do not import Books.
- **Books is in the core**, like reports: it may import the practice
  apps' models to post from them, and the case builder may not import
  it. The import-linter contracts in `pyproject.toml` say so.
- **It is a module the firm can switch off**, `Firm.books_enabled`,
  under Settings > Features beside the case file and the library, and
  off by default: a firm that keeps its books elsewhere never sees it.
  Off, `/books/` and `/settings/books/` answer 404.
- **It is gated by a permission of its own**, `perm_books`, off by
  default, so most staff never see it. An outside bookkeeper is a user
  with Books and nothing else. Settings > Books (the tax return and the
  basis) is admin-only.
- **One sidebar entry, Books**, in the module section below the rule,
  with sub-navigation of its own: Accounts, Journal, Statements now;
  Bank, Reconcile and Bills to come. Nothing in Invoicing or Reports
  moves. The line is: Invoicing is the receivables workflow staff run
  day to day, matter-facing; Books is the bookkeeping behind it,
  firm-facing. Reports stays practice performance (activity, revenue,
  realization, aging) built from time and invoices; Books carries the
  statements built from the ledger. The Revenue report and the profit
  and loss will look alike and are not the same number; both stay.
- **Trust is the hybrid.** Recording a deposit or disbursement stays in
  Invoicing > Trust. The three-way reconciliation (bank statement,
  trust ledger, sum of client balances) belongs in Books.
- **Every income and expense account carries a tax line for each return
  the firm might file**: Schedule C and Form 1120-S. The firm's return
  is a setting (`Firm.tax_form`); the Tax Summary and, later, the TXF
  export read the mapping for that form. The owner is an LLC
  considering a late S-corporation election, so the chart ships ready
  for both: officer compensation, payroll, a structured equity section,
  a shareholder loan account. Balance-sheet accounts carry no tax line;
  Schedule L is derived from the subtype.
- **Cash basis is the default** (`Firm.accounting_basis`). Small firms
  file on it and TurboTax's Schedule C assumes it. Under cash basis the
  posting rules will recognise revenue when a payment lands, not when
  an invoice goes out; the receivable account exists for accrual.
- **Two law-firm facts are in the chart, not left to the bookkeeper.**
  Client trust money is a liability, never income. Costs advanced for a
  client are an asset until repaid (and the repayment is not income);
  only a write-off is an expense.
- **The year-end handoff is a package, not an integration.** An
  accountant takes a trial balance with tax lines, the statements,
  general-ledger detail, the reconciliations and a 1099 summary, as
  spreadsheets and PDFs. TurboTax desktop imports TXF; TurboTax Online
  imports nothing and takes the Tax Summary's lines by hand. The Tax
  Summary exists from the first slice so the mapping is proven early.

## Alternatives

- **A third project in its own repository**, borrowing from both. Set
  aside: for a law practice the accounting is dominated by what Kosmos
  already owns (receivables, trust, cost advances), so a separate app
  would spend most of its effort re-importing Kosmos data over an API,
  and every new Kosmos feature would reopen that seam. The finance
  project's bank-feed code is the smaller, more portable half and can
  be ported in.
- **A separate shell or login for Books.** Rejected for the reasons in
  [The "two shells" redesign is abandoned](2026-10-05-two-shells-redesign-abandoned.md);
  the one case for it, a bookkeeper who should see nothing else, is a
  permission.
- **Folding Invoicing and the financial reports into Books.** Rejected:
  staff who bill are not bookkeepers, and a payment is still recorded
  where the matter is. Books sees it land in the bank feed and matches
  it, which is how QuickBooks itself sits next to a practice manager.
- **Extending the trust ledger or the finance project's categorised
  transactions into the general ledger.** Rejected: both are
  single-entry. The ledger is new code at the centre, and the existing
  records post into it.

## Consequences

- A practice-app event that should reach the books is a posting rule in
  `apps/books` (a signal handler or a small service call), not a line in
  the practice app. The posting rules look accounts up by role
  (`Account.role`: operating bank, receivable, trust liability, and so
  on), one account per role, so a firm may rename or renumber its chart.
- A sourced entry (`JournalEntry.source` other than manual) is corrected
  by a reversing entry, never edited or deleted; the `(source,
  source_id)` pair is unique, so a record posts once.
- The next slices, in order: posting from payments, trust and expense
  entries; the bank feed ported from the finance project (Plaid, CSV,
  payee rules, transfer matching) and bank reconciliation; bills and
  vendors with the 1099 summary; the year-end package and the TXF
  export; the trust three-way reconciliation.

## Evidence

- The owner's requests of 2026-10-22: the project, the placement, the
  tax handoff, the LLC and the possible S-corporation election.
- `apps/books/models.py`, `chart.py`, `ledger.py`, `tax_lines.py`.
- `apps/settings/features/__init__.py` (`books_enabled`),
  `apps/accounts/middleware.py` (`BOOKS_PATTERN`, the `/books/`
  permission path), `templates/sidebar.html`.
- The migrations `books.0001_initial`, `settings.0016_books`,
  `accounts.0025_books`.

## Related

- [Books](../dev/subsystems/books.md).
- [The case builder is a module with its own navigation (2026-10-19)](2026-10-19-the-case-builder-is-a-module-with-its-own-navigation.md): the module pattern Books follows.
- [Trust available is client-level and uses the pending balance (2026-07-03)](2026-07-03-trust-available-client-level-pending.md).
- [The reports permission opens the reports (2026-10-02)](2026-10-02-reports-permission-opens-the-reports.md).
