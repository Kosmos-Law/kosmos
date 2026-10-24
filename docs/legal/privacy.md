# Privacy policy

This policy says what Kosmos does with data, with particular attention
to the QuickBooks Online connection. It is short because the
arrangement is simple: a firm's data lives on the firm's own server.

## Who holds the data

Each firm runs its own Kosmos server. Everything Kosmos stores, the
firm's matters, documents, time, invoices and books, is in a database
on that server, under the firm's control, and is backed up where the
firm chooses. The Kosmos project, the authors of the software, operates
no servers for firms, receives none of their data, and cannot see it.

## What the QuickBooks Online connection reads

When an administrator connects the firm's QuickBooks Online company,
Kosmos reads, through Intuit's API:

- the company's name and fiscal year;
- the chart of accounts, every account including inactive ones;
- every transaction, as the lines of QuickBooks's Journal report: the
  date, type, number, the customer or vendor name, the memo, and the
  accounts and amounts;
- the trial balance, to check that the copy agrees with QuickBooks.

Kosmos reads nothing else from the company and writes nothing to it.

## Where it goes and who sees it

The data read from QuickBooks is stored in the firm's own Kosmos
database, beside the firm's other records. It is shown to the firm's
users who hold the Books permission, which an administrator grants.
Nothing is sent to anyone else: not to the Kosmos project, not to any
third party, and not back to Intuit beyond the requests that read it.

The sign-in tokens Intuit issues are stored in the same database,
encrypted with a key derived from the server's secret, and are used only
to make those requests.

## How long it is kept

The copied chart and transactions stay in the firm's database for as
long as the firm keeps them; they are the firm's records. Disconnecting
QuickBooks revokes the tokens with Intuit and deletes them from the
database; the copied records remain until the firm removes them.

## Everything else

Kosmos's other integrations, email, Google Workspace, payment
processors and AI providers, are each optional, each connected by the
firm with its own accounts, and each described in the
[operator guide](../admin/index.md), which says what each one sends and
where. A firm's duties to its clients and to the law regarding the data
it holds are the firm's own.

## Questions

Write to [info@kosmos.law](mailto:info@kosmos.law).
