# Trust accounting

This page is for the attorney or office manager who looks after client
money held in trust. It covers how to record deposits and withdrawals,
what each balance means and how it is worked out, and what Kosmos does not
do for you.

## Whose money it is

Every trust transaction is recorded against a client (a contact), never
against a matter. A client has one trust balance, and all of that client's
matters share it. If Elena Rivera has two matters, both show the same
trust figures, and unbilled work on either one lowers **Trust Available**
on both. Kosmos keeps no separate balance for a matter. To show which
matter a deposit or withdrawal relates to, say so in **Description**.

## Who can see and record trust activity

You need the Financial permission for the **Trust** tab and everything on
it. Ask your administrator. Every user with that permission can record,
edit, confirm and delete any trust transaction.

Two trust figures are shown without that permission: the balances on a
contact's **Trust** tab (to every user) and **Trust Available (Pending)**
on the time entry form (to every user who can open the matter). **Low
Trust Available (Pending)** on the Dash is shown to administrators only.

## The Trust tab

Click **Invoicing** in the sidebar, then **Trust**. The tab has three
views: **Summary**, **History** and a single client's ledger.

### Summary

**Summary** has one row for each client, 50 to a page.

| Column | What it shows |
|---|---|
| **Client ID** | The contact's number in Kosmos. |
| **Client** | The client's name. Click it to open that client's ledger. |
| **Pending Balance** | Deposits less withdrawals, counting every transaction. Highlighted when it differs from **Confirmed Balance**. |
| **Confirmed Balance** | Deposits less withdrawals, counting confirmed transactions only. |
| **Available (Pending)** | The client's trust available. See [The three figures](#the-three-figures). |

Click the sort button beside any column except **Client ID** to sort by
it, and again to reverse the order. The list starts sorted by client name.
There is no search or filter on this view.

A client is listed while its deposits (confirmed or not) differ from its
confirmed withdrawals. So a client whose money has all been paid out stays
on the list until the withdrawals are confirmed, then leaves it.

Good to know:

- In the **Total** row, **Pending Balance** and **Confirmed Balance** add
  up every transaction in the ledger, including clients who are not
  listed. **Available (Pending)** adds up the listed clients only.

### History

**History** lists transactions for all clients, newest first, 50 to a
page. It opens on **30 days**. Click **60 days** or **All** for a longer
period. The columns are **Client ID**, **Date**, **Client**,
**Description**, **Method**, **Deposit**, **Withdrawal** and **C**
(confirmed). **Pending Balance** and **Confirmed Balance** under the table
are for the whole trust ledger, whichever period is showing.

### A client's ledger

Click a client's name on **Summary** or **History**. The ledger lists
every transaction for that client on one page, oldest first, with
**Date**, **Description**, **Method**, **Deposit**, **Withdrawal** and
**C**. Under the table are the client's **Pending Balance** and
**Confirmed Balance**. The client's name in the toolbar opens the contact.

## Record a deposit

1. Click **Invoicing** in the sidebar, then **Trust**.
2. Click the plus button at the left of the toolbar, then **Add
   Transaction**.
3. Choose the **Client** and leave **Type** on **Deposit**.
4. Check the **Date** and **Method**, type a **Description**, enter the
   **Amount** and click **Submit**.

The form closes and the view refreshes with the new figures.

| Field | Required | Notes |
|---|---|---|
| **Client** | Yes | On **Summary** and **History** the list holds current clients only: contacts who are the client on an **Open** or **Complete** matter. On a client's ledger the client is already chosen. |
| **Date** | Yes | Starts as today. |
| **Type** | Yes | **Deposit** or **Withdrawal**. These are the only two types. |
| **Method** | No | **ACH**, **Card**, **Wire**, **Transfer** or **Check**. Starts on **Check**. |
| **Description** | Yes | 255 characters at most. Shown in every list, and the link you click to edit the transaction. |
| **Amount** | Yes | Digits only, such as 2500.00. A dollar sign or a comma is refused. |
| **Confirmed** | Yes | **No** (the default) or **Yes**. See [Pending and confirmed](#pending-and-confirmed). |

Good to know:

- To record a transaction for a client who is not in the **Client** list
  (one whose only matter is **Pending**, or a former client), open that
  client's ledger and add it there. If the client has no transactions
  yet, open the matter's **Ledger** tab and click the amount beside
  **Client Trust Balance (Pending)**.

## Record a disbursement or a refund

Kosmos has no separate types for a payment to a third party, a refund to
the client or a transfer of earned fees. Each is a **Withdrawal**, and
**Description** is where you say which.

1. Open the client's ledger and click the plus button, then **Add
   Transaction**.
2. Set **Type** to **Withdrawal**, fill in **Date**, **Method**,
   **Description** and **Amount**, and click **Submit**.

The withdrawal appears in the **Withdrawal** column and the balances drop.

Good to know:

- Kosmos does not compare a withdrawal with the client's balance. A
  withdrawal larger than the balance is saved, and the balance then shows
  as a negative amount.

## Pay an invoice from trust

This records a transfer from trust to your operating account in payment
of an invoice. The invoice must be **Sent** or **Deferred**. See
[Invoicing](invoicing.md) for how to find and open an invoice.

1. Open the invoice and click **+ Trust** beside its status. **Add
   Payment** opens with **Payment method** set to **Trust** and **Detail**
   set to the invoice number.
2. Check **Amount**. It starts as the invoice's total, not what is still
   unpaid.
3. Click **Submit**. Kosmos takes you to **Payments**.

Kosmos records two things:

- **A payment on the matter**, with the date, method, amount and detail
  from the form. It is applied to the invoice, up to what the invoice
  still owes. An invoice paid in full becomes **Paid**.
- **A trust withdrawal for the matter's client**, dated today whatever
  **Date** you entered, for the whole **Amount**, with the description
  "Invoice" and its number, no method, and not confirmed.

Good to know:

- The two records are not linked afterwards. If you edit or delete the
  payment, or void the invoice, the trust withdrawal stays as it is.
  Correct it yourself on the client's ledger.
- Only **+ Trust** records a withdrawal, and it does so whichever
  **Payment method** you leave on the form. Choosing **Trust** as the
  method under **+ Card**, or in **Add Payment** on the **Payments** tab,
  records the payment and no withdrawal.
- Use **+ Trust** only on a matter that has a client. On a matter with no
  client the withdrawal belongs to no one, and the **Trust** tab stops
  opening until someone with access to the server removes it.

## Pending and confirmed

Each transaction is either confirmed or not. **Confirmed** is a mark you
set, meant for a transaction that has cleared the bank. Kosmos does not
check it against anything. There is no separate "pending" mark: **Pending
Balance** counts every transaction, and **Confirmed Balance** counts the
confirmed ones only.

To confirm a transaction, click the box in the **C** column on **History**
or the client's ledger, or set **Confirmed** to **Yes** in the form. Click
the box again to undo it. The change is saved at once, with no question
asked. It changes **Confirmed Balance** wherever that is shown. It does
not change **Pending Balance** or **Trust Available**.

## The three figures

| Figure | How it is worked out |
|---|---|
| **Pending Balance** | All of the client's deposits less all of the client's withdrawals, confirmed or not. |
| **Confirmed Balance** | The client's confirmed deposits less the client's confirmed withdrawals. |
| **Trust Available** | **Pending Balance**, less what the client owes on invoices, less the client's work in progress. |

For **Trust Available**, Kosmos takes the client's **Pending Balance** and
subtracts, across all of that client's matters:

- **What is owed on invoices.** For each invoice that is not **Draft** or
  **Approved**: its total, less the payments and credits applied to it.
  Invoices marked **Deferred**, **Void** or **Uncollectible** are not
  subtracted.
- **Work in progress.** Time, expenses and flat fees that are not marked
  **Comp** and are either not on an invoice (and not marked **Entered**)
  or on a **Draft** or **Approved** invoice, less any discount on those
  invoices. Matters with **Deferred Fee Arrangement** set to **Yes** are
  left out of this part.

For example, Elena Rivera has $5,000.00 in trust. One sent invoice has
$1,200.00 unpaid, and $800.00 of time on Rivera v. Northside Logistics is
not billed yet. Her **Trust Available** is $3,000.00, on every one of her
matters. A matter with no client shows $0.00.

| Where | Label | Figure |
|---|---|---|
| **Trust** → **Summary** | **Available (Pending)** | Trust available |
| A matter's **Overview**, under **Financials** | **Trust Available** | Trust available |
| A matter's **Ledger** | **Client Trust Balance (Pending)** and **Trust Available (Pending)** | Pending balance and trust available |
| The time entry form, under **Matter** | **Trust Available (Pending)** | Trust available |
| The Dash, under **Collections** | **Low Trust Available (Pending)** | Trust available |
| **Invoicing** → **Work in Progress** | **Trust (Pending)** | Pending balance |
| An invoice sent to the client | **Retainer Balance** | Confirmed balance, shown only when above zero |
| The matter ledger PDF | **Funds on Retainer** | Confirmed balance |

Good to know:

- **Trust Available** counts deposits that are not confirmed yet. It can
  be higher than the money that has cleared.
- On **Work in Progress**, every matter of a client shows that client's
  whole balance, and the **Total** row adds each row. A client with two
  matters in the list is counted twice in that total.

## Low-trust warnings

Kosmos warns by colour and by a list on the Dash. It never stops you
recording time, an invoice or a withdrawal.

- **Overview**, **Ledger** and **Summary**: the trust available figure
  takes a warning colour when it is below 25% of the client's **Pending
  Balance** (under $1,250.00 for a $5,000.00 balance), and an alert
  colour when it is below zero. The colours depend on your theme.
- **The time entry form**: the figure takes the alert colour when it is
  below zero.
- **The Dash**: **Low Trust Available (Pending)** lists up to ten matters,
  lowest first, with negative figures highlighted. A matter is listed
  when it is **Open** and billable, has unbilled time or expenses, is not
  a deferred fee matter, has no **Deferred** invoice, and its client's
  **Pending Balance** is above zero with less than $1,000.00 available.
  Click a matter to open its **Ledger**.

## Online trust deposits

If your firm takes payments online, click the plus button on the **Trust**
tab, then **Request Deposit**, to email a client a link for a deposit.
[Payments](payments.md) covers the request itself.

When the client pays, Kosmos adds a **Deposit** to the client's ledger. Its
**Method** is **Card** or **ACH**, and its description starts "Online
trust deposit". It counts in **Pending Balance** and **Trust Available**
at once. As a rule it starts unconfirmed, and Kosmos confirms it when the
payment processor reports that the money has reached the trust bank
account. **Edit Transaction** shows the processor's **Transaction ID**.

Good to know:

- If the payment is later returned and the deposit is still unconfirmed,
  Kosmos deletes the deposit. If you had already confirmed it, the
  deposit stays in both balances with nothing on the ledger to mark it as
  returned, and you must record the correction yourself.

## Edit or delete a transaction

Anyone with the Financial permission can edit or delete any transaction,
confirmed or not, including an online deposit.

1. On **History** or the client's ledger, click the transaction's
   **Description**. **Edit Transaction** opens with the same fields as
   **Add Transaction**.
2. Change the fields and click **Submit**. Or click **Delete**, then
   confirm "Are you sure you want to delete this record?".

A deleted transaction is gone from every list, balance and export.

Good to know:

- No screen shows who recorded, changed or deleted a transaction. Kosmos
  keeps that history internally, and the person who runs your Kosmos
  server can retrieve it.
- Deleting a contact deletes its trust transactions with it. See
  [Contacts](contacts.md).

## Export the ledger

On **History**, click **Download CSV**. The file holds the whole trust
ledger, whichever period is showing, oldest first, with **Client ID**,
**Date**, **Client Name**, **Description**, **Method**, **Amount**,
**Type** and **Confirmed**. Withdrawals are negative amounts, so
**Amount** adds up to the **Pending Balance** of the whole ledger.

!!! note

    Kosmos does not reconcile the trust account. It has no three-way
    reconciliation, no bank statement import or matching, no trust report
    under **Reports** and no printable statement of a client's trust
    ledger. The CSV is the only export of trust transactions.

## Trust on a contact and on a matter

A client's contact page has a **Trust** tab showing **Confirmed Balance**
and **Pending Balance**. **View Full Trust Ledger** opens the client's
ledger and needs the Financial permission. A contact with no transactions
shows "This contact has no trust account activity."

A matter's **Ledger** tab shows **Client Trust Balance (Pending)** and
**Trust Available (Pending)** beside the matter's own totals. Both are the
client's figures, shared with the client's other matters. Click the
balance to open the client's ledger. See [Matters](matters.md#ledger).
