# Books

`apps/books` is the firm's general ledger: a chart of accounts, journal
entries and the statements. It is a module (Settings > Features, off by
default) gated by the Books permission, with its own sub-navigation
under `/books/`: Accounts, Journal, Statements. The record is [Books is
the ledger behind invoicing and trust](../../decisions/2026-10-22-books-is-the-ledger-behind-invoicing-and-trust.md).

## The models

| Model | Table | What it is |
|---|---|---|
| `Account` | `app_books_account` | One account in the chart: a code, a type (asset, liability, equity, income, expense), a subtype that places it on the statements and on Schedule L, an optional parent (a sub-account shares its parent's kind; `full_name` is the path), an optional role the posting rules look up (one account per role), and a tax line for each return (`schedule_c_line`, `form_1120s_line`; blank on balance-sheet accounts). Inactive accounts keep their history and take no new lines. |
| `JournalEntry` | `app_books_entry` | A dated, balanced set of lines with a memo. `source` says what produced it: manual, or a practice record (invoice, payment, credit, trust, expense), a bank transaction, QuickBooks, or a reversal. `(source, source_id)` is unique, so a record posts once; `source_ref` is the key when it is not a row id (a QuickBooks transaction's type and id), unique the same way. `reverses` points at the entry a reversal undoes. |
| `QuickBooksConnection` | `app_books_quickbooks` | The firm's QuickBooks Online company while Books mirrors it (one row): the realm id, the company's name, the environment (sandbox or production) the tokens were issued for, the tokens sealed at rest (`utils/crypto.py`; `access` and `refresh` read them), their expiries, who connected it, and the last sync's time and error. |
| `JournalLine` | `app_books_line` | One debit or one credit to one account (a check constraint forbids both and negatives), with an optional contact and matter as the sub-ledgers: the client whose trust money moved, the matter whose cost was advanced. |

There is no stored balance. `Account.balance(as_of, since)` sums the
lines on the account's normal side (debit for assets and expenses,
credit for the rest).

## Posting

`apps/books/ledger.py` is the one way into the ledger:

- `post(date, memo, lines, source, source_id)` checks the lines balance
  (at least two, debits equal credits, something moves, no inactive
  account) and writes the entry and lines in one transaction.
- `reverse(entry, date)` posts the mirror image and links it; an entry
  reverses once.
- `replace_lines(entry, lines)` is for editing a manual entry; sourced
  entries are never edited or deleted, only reversed. The views enforce
  that too.
- `account_for(role)` and `require_account(role)` find the account a
  posting rule needs.

The posting rules for the practice apps (payments, trust transactions,
expense entries) are the next slice; they will live in this app and
listen to the practice apps, never the other way round.

## Statements

Also in `ledger.py`, all computed from the lines:

- `trial_balance(as_of, year_start=None)`: every account with a
  balance in debit and credit columns; a contra balance (an overdrawn
  bank) swaps columns. With `year_start`, income and expenses show the
  year only and earlier years fold into retained earnings.
- `profit_and_loss(start, end)`: income and expense rows and the net.
- `balance_sheet(as_of, year_start)`: assets, liabilities and equity,
  with two computed equity rows, retained earnings (the net of every
  period before `year_start`) and the year's net income. There are no
  closing entries.
- `general_ledger(account, start, end)`: the account's lines with a
  running balance and the balance brought forward.
- `schedule_l_line(account)`: the Form 1120-S balance-sheet line, from
  the subtype and role.

The Tax Summary view (`views._tax_summary`) folds the profit and loss
onto the lines of the firm's return (`Firm.tax_form`) using the
account's tax line for that form, and lists accounts with activity that
the return has no line for.

## The default chart

`apps/books/chart.py` holds `DEFAULT_CHART`, a law-firm chart on the cash
basis ready for an LLC or an S corporation, and `seed_default_chart()`,
which adds the accounts whose code is missing and leaves a renamed or
removed one alone. The empty Accounts page offers it; `manage.py
seed_chart` runs it from the shell. The chart's law-firm specifics:
trust money is a liability, advanced client costs are an asset, officer
compensation has no Schedule C line.

## Coming over from QuickBooks Online

`apps/books/quickbooks.py` reads three of QuickBooks's standard reports
exported to Excel and two commands drive it:

- `manage.py import_quickbooks --accounts <Account List.xlsx>
  [--journal <Journal.xlsx>] [--dry-run] [--reset-chart]`. The Account
  List becomes the chart, sub-accounts included (`Account.parent`), with
  the kind from QuickBooks's account type (`QB_TYPE_SUBTYPE`), the tax
  lines from its detail type and the account's name
  (`DETAIL_TAX_LINES`, `NAME_TAX_LINES`) and the roles from name
  patterns (`ROLE_RULES`), one account per role, a leaf before a parent.
  The Journal, exported with the period set to All Dates, posts every
  transaction as an entry with source `quickbooks` and QuickBooks's own
  transaction id as `source_id`, so running it again adds nothing. Any
  problem (an account the chart lacks, an unbalanced transaction) stops
  the journal import before anything is written. `--dry-run` prints the
  decisions; `--reset-chart` drops a chart nothing is posted to, for a
  server that seeded the default chart first.
- `manage.py compare_quickbooks --trial-balance <Trial Balance.xlsx>`
  sets the ledger's trial balance as of the report's own date beside
  QuickBooks's, account by account, and exits 1 when anything differs.
  Income and expenses are the year's, with earlier years folded into
  retained earnings (`ledger.trial_balance(as_of, year_start)`), which
  is how QuickBooks presents a trial balance after its year-end close.

The firm's own exports stay outside the repository; the tests
(`test_quickbooks.py`) build small workbooks of the same shape.

## The QuickBooks connection

Until cut-over Books mirrors QuickBooks Online (the amendment of
2026-10-24 to the decision record): the chart and every entry come from
its API, entries with source `quickbooks` are replaced or removed as the
bookkeeper changes them, the interface is read-only, and no practice-app
event posts. `apps/books/intuit.py` is the connection:

- `configured()` reads `QUICKBOOKS_CLIENT_ID` and `QUICKBOOKS_CLIENT_SECRET`
  from config/.env; `environment()` reads `QUICKBOOKS_ENVIRONMENT`
  (`sandbox` or `production`), which decides only new connections.
- `endpoints(env)` reads the OAuth endpoints (authorize, token, revoke)
  from Intuit's discovery document for the environment, once a day, and
  keeps the known ones while the document cannot be read.
- `authorize_url(redirect, state)` starts Intuit's OAuth 2.0 with the
  accounting scope; `connect(code, realm_id, redirect, user)` trades the
  code for tokens, keeps them as the one `QuickBooksConnection` (an
  earlier one is deleted) and asks the company its name.
- `refresh(conn, refused=False)` posts the refresh token under a row
  lock, since Intuit issues a new refresh token on each refresh and
  revokes the connection if an old one is reused; `invalid_grant` raises
  `ConnectionLost`, which means an administrator must connect again.
- `Client(conn)` calls the company's API on the host for its
  environment, refreshing an access token within five minutes of expiry
  and once more after a 401: `company_info()`, `query(statement)` and
  `report(name, **params)` (the standard reports, as Intuit's column/row
  JSON). Anything but a 200 raises `QuickBooksError`, whose message
  carries Intuit's reason and the `intuit_tid` response header its
  support looks a problem up by; the sync records it on the connection
  and logs it.
- `disconnect()` revokes at Intuit (a failure is logged, not raised) and
  deletes the row.

The views are `apps/settings/integrations/quickbooks.py` (connect, the
`/settings/quickbooks/store` callback, which must match the redirect URI
registered on the developer portal, and disconnect), admin-only and 404
while Books is off (`BOOKS_PATTERN` in the middleware); the Integrations
page includes `settings/integrations/quickbooks.html` for an
administrator while Books is on. Tests: `test_intuit.py` (against a stub
of `requests`) and `apps/settings/tests/test_quickbooks.py`.

## The sync

`apps/books/sync.py` keeps Books the same as the company, in three steps
`run(conn)` takes in order and records on the connection (`last_sync_at`,
`last_sync_summary`, `last_sync_error`):

- `sync_chart(items)`: every account of the company, inactive ones
  included (`fetch_accounts` asks for them), is an account here, found by
  `Account.quickbooks_id`. A new one gets its kind from the API's account
  type (`API_TYPE_LABEL` maps it onto the export's names, then
  `quickbooks.subtype_for`), its tax lines from the detail type
  (`DETAIL_LABELS`, then `quickbooks.tax_lines_for`), QuickBooks's
  account number as its code or, without one, the next free number in
  its type's range (`CODE_BASE`: assets 1000, liabilities 2000, equity
  3000, income 4000, expenses 5000), and its parent from `ParentRef`,
  whose kind it shares. An existing one follows its name, parent, kind,
  description and active flag; its code, tax lines and role are left
  alone. `_assign_roles` then gives every role no account holds to the
  mirrored account that fits it (`quickbooks.ROLE_RULES`), so a role
  moved on the Accounts page sticks and one cleared comes back.
- `sync_journal(transactions)`: the Journal report
  (`read_journal_report`, every row of every transaction, a totals row
  between transactions) becomes entries with source `quickbooks` and
  `source_ref` "<type>:<id>" ("Invoice:91"; QuickBooks numbers each type
  from one). A new transaction is posted (`ledger.post` with
  `allow_inactive`, since history on a since-closed account is still
  history); one whose date, memo or lines changed has them replaced in
  place; one the report no longer has is deleted. These entries are the
  sync's, not the reversal-only kind. A transaction naming an account
  the chart lacks, or whose lines do not balance, is reported and left
  as it was, and nothing else is affected.
- `compare_trial_balance`: the ledger's trial balance for the fiscal
  year (`QuickBooksConnection.fiscal_year_start`, from the company's
  `FiscalYearStartMonth`) to today, with earlier years folded into the
  retained earnings account, beside QuickBooks's Trial Balance report
  for the same period (`read_trial_balance`), by QuickBooks account id.
  The summary names the first account that differs.

`scheduled_sync` runs it every thirty minutes (`quickbooks-sync` in
`apps/management/schedules.py`) and does nothing without a connection;
`books:sync` (`views.books_sync`) runs it on demand from the line under
the Books sub-navigation (htmx: the lists reload and a toast carries the
summary) and from Settings > Integrations (a form: the page comes back
with the summary in a toast).

While the connection exists Books is read-only: `views._mirrored` refuses
the seed, add, edit, delete and reverse views with a 400, and the
templates leave the buttons out (`books_mirror`, the connection, is in
every template's context from `config/context.py`). Accounts may still
be edited, for their roles and tax lines. The export-file import above
is the fallback for a firm with no API connection; it must not be
combined with the mirror, whose first sync would remove its entries
(they carry no `source_ref`).

## Settings and gates

- `Firm.books_enabled` (Settings > Features), read through
  `apps.settings.features.books_enabled()`; off, the middleware 404s
  `/books/` and `/settings/books/`, and the sidebar has no entry.
- `CustomUser.perm_books` (Settings > Permissions); the middleware's
  `PERMISSION_PATHS` refuses `/books/` without it.
- `Firm.tax_form` and `Firm.accounting_basis` (Settings > Books, admin
  only).
- `/settings/quickbooks/` is admin-only and, like `/books/`, 404 while
  Books is off.

## Templates and styles

`templates/books/main.html` is the shell with the sub-navigation;
`accounts/`, `journal/` and `statements/` hold the pages, each a full
page that includes a list partial re-fetched on `booksChanged`.
The Accounts page is a tree, type then kind (the subtype) then account,
with a total on every branch; which branches are folded and whether
inactive accounts show are kept in the session (`books_tree_collapsed`,
`books_tree_show_inactive`) through the `tree-toggle`, `tree-fold` and
`tree-inactive` views, the shape of the fin project's accounts tree.
`templates/books/period.html` is the from/to control, a GET so the
period is in the address. Styles are in `static/css/apps/books.css`.

## Tests

`apps/books/tests/`: `test_ledger.py` (posting rules and the
statements), `test_chart.py` (the default chart and its tax lines),
`test_views.py` (the switch, the permission, the pages and the forms).
