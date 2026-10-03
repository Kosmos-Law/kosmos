# Invoicing

This page is for the people who bill clients: attorneys and office
managers. It covers how to turn recorded work into invoices, send them,
and follow each one until it is paid, written off or voided. Read
[Time and expenses](time-and-expenses.md) first: it explains entries,
**Comp** and **Entered**.

## Open Invoicing

Click **Invoicing** in the sidebar. You need the Financial permission for
this. Ask your administrator. It opens on **Invoices** and has seven tabs.

| Tab | What it is for |
|---|---|
| **Work in Progress** | Matters with work that is on no invoice yet. You create invoices here. |
| **Invoices** | Every invoice, with its status and what is still owed on it. |
| **Payments** | Money received. See [Payments](payments.md). |
| **Credits** | Amounts taken off what a client owes without money changing hands. |
| **Collection** | Matters with a balance to collect. |
| **Trust** | Client funds held in trust. See [Trust](trust.md). |
| **Requests** | Requests for payment emailed to clients, and paying online. See [Payments](payments.md). |

Invoicing covers every matter in the firm. If you are limited to assigned
matters, you still see the other matters' invoices and figures here.

## See what is ready to bill

**Work in Progress** lists each billable matter that has unbilled work,
20 to a page, largest **Activity** first. **Count** shows how many match.

| Column | What it shows |
|---|---|
| **Matter** | Click the name to open the matter's **Ledger** tab. |
| **Hours**, **Fees** | Unbilled time: the hours, and hours times rate. |
| **Flat Fees**, **Expenses** | Unbilled flat fee and expense amounts. |
| **Activity** | **Fees** plus **Flat Fees** plus **Expenses**. |
| **Trust (Pending)** | The client's trust balance, counting transactions not yet confirmed. See [Trust](trust.md). |
| **Last Inv.** | The issue date of the matter's latest invoice. |

How the figures are arrived at:

- An entry counts when **Entered** is **No** and it is on no invoice. Once
  an invoice picks it up, even a draft, it leaves this tab.
- Comp entries are left out of every column, hours included.
- Matters that are not billable are not listed.
- The **Totals** row covers every matter that matches, not only the page.

To narrow the list, click the period button and choose **All Activity**,
**Current Month** or **Prior Month**: the figures then count only entries
dated in that period. **Filter** opens **Filter Work in Progress**, with
**Activity Period**, **Sort By** and **Last Invoice Before** (matters
whose latest invoice is dated on or before that day, or that have none).
The sort buttons beside **Matter**, **Activity** and **Last Inv.** reorder
the list.

Good to know:

- **Work in Progress** on a matter's **Overview** and **Ledger** is a
  larger figure. It adds the work sitting on that matter's Draft and
  Approved invoices, less any discount on them.
- **Prior Month** counts every entry dated before the first day of this
  month, not only last month's.
- Every matter of a client shows that client's whole **Trust (Pending)**
  balance. The **Totals** row counts each client once, so it can be less
  than the column added up.

## Create an invoice

1. Click **Invoicing** → **Work in Progress**, then the plus button at the
   left of the toolbar. **Add Invoice** opens.
2. Choose the **Matter**. Each matter is followed by its unbilled amount.
3. Check **Limit Date** and **Issue Date**, fill in the other fields that
   apply, and click **Submit**.

The form closes, and the work the invoice took leaves the list. The new
invoice is a draft: click **Invoices**, which now shows **Draft**.

| Field | Notes |
|---|---|
| **Matter** | Required. Billable matters with unbilled time, expenses or flat fees. |
| **Limit Date** | The invoice takes work dated on or before this day. Starts as the last day of last month. |
| **Issue Date** | The date printed on the invoice. Starts as today. |
| **Message** | Optional. Printed on the invoice under **Client Message**, and offered as the text of the email when you send it. |
| **Comment** | Optional. A note for the firm, shown on the invoice's **Details** tab. The client does not see it. |
| **Show comp** | **Yes** (the default) lists comp entries on the PDF and shows them being taken off. **No** leaves them off the PDF. |
| **Discount** | A dollar amount taken off the total. Leave it at 0 for none. |

A draft takes every time, expense and flat fee entry on the matter that is
dated on or before **Limit Date**, has **Entered** at **No** and is on no
invoice. Comp entries come too, at no charge. Hourly and flat-fee matters
are invoiced the same way. A flat fee is billed only when a flat fee entry
has been recorded: the matter's **Flat Fee Amount** alone bills nothing.

To invoice several matters at once, tick the box beside each matter on
**Work in Progress** (the box in the heading selects the page), click
**Create Invoices**, set **Limit Date** and **Issue Date**, and click
**Create Invoices**. Each matter gets its own draft.

Good to know:

- A draft takes in new work only when it is saved again: open **Edit
  Invoice** and click **Submit**, or set its status to **Draft** again.
- Kosmos creates the invoice even when there is nothing to put on it.

## Check and correct a draft

Click an invoice's **ID** in the **Invoices** list. The page is headed
with the invoice number and matter, for example "Invoice 123 - Rivera v.
Northside Logistics", and opens on **Time**.

| Tab | What it shows |
|---|---|
| **Details** | The **Comment**, then **Date Limit**, **Created by**, **Created at**, **Issue date**, **Total amount**, **Status** and **Discount**. |
| **Time**, **Expenses**, **Flat Fees** | The entries on the invoice, ten to a page, with totals, comp and net figures below. |
| **Review** | The PDF as the client will get it. A draft's PDF is marked as a draft. |
| **History** | **Delivery History** (each email) and **Payment History** (payments and credits applied), with **Invoice total** and **Outstanding**. |
| **Ledger** | The matter's ledger, if you can see the matter. |

While the invoice is a draft you can change what is on it:

- Click an entry's text to edit or delete it. A comp entry shows "comp"
  in place of its amount.
- On **Time**, tick entries, click **Comp** and choose **Comp** or **Not
  Comp**.
- Click the pencil button at the top right for **Edit Invoice**, which
  has **Date limit**, **Date issued**, **Message**, **Comment**, **Show
  comp** and **Discount**.

**Total amount** is time not marked comp (hours times rate), plus flat
fees and expenses not marked comp, less **Discount**. The PDF calls it
**Total Due (Please Pay)**. In the **Invoices** list it is **Total**, and
**Amount Due** is **Total** less the payments and credits applied to that
invoice. **Fees** in the list is time only: a flat fee shows in **Total**.
Under the list, **Total Charges** adds time, flat fees and expenses before
discounts, for every invoice the list is showing.

If the client has confirmed money in trust, the PDF adds **Funds in
Trust** with the client's **Retainer Balance**. Under it the PDF prints
the **Invoice Trust Note** that an administrator has entered on
**Settings → Firm**. Until a note is entered, the balance prints alone.
See [Settings](settings.md#firm).

Good to know:

- Nothing takes a single entry off a draft and leaves it unbilled, and
  an earlier **Date limit** does not drop entries. Delete the draft and
  create it again with the limit you want.

## Move an invoice through its statuses

Click the status in the **Invoices** list or at the top of the invoice
and choose **Draft**, **Approved**, **Sent**, **Deferred** or
**Uncollectible**. The change is made at once. The list starts on
**Sent**. Click **Draft**, **Approved**, **Deferred**, **Paid** or
**Void** to see the others, or use **Filter** → **Status** for
**Uncollectible** and **All**.

| Status | What it means and what it changes |
|---|---|
| **Draft** | Being prepared. Entries can be edited. Not on the matter's ledger, and not owed. |
| **Approved** | Checked and ready to send. Its entries can no longer be edited or deleted, and Kosmos keeps the PDF made now. Still not owed. The pencil button still works. |
| **Sent** | Issued. On the ledger and in **Balance Due**. Payments and credits can be applied. The pencil button is gone. |
| **Deferred** | Issued, but not being collected for now. Still in **Balance Due**, shown apart on the ledger, and left out of **Due** on **Collection**. |
| **Paid** | Set by Kosmos when the payments and credits applied equal the total. Removing one in the **Apply** dialog, or deleting the payment or credit, returns the invoice to **Sent**. |
| **Uncollectible** | Written off. Out of **Balance Due**. Its entries stay billed. **Amount Due** in the list and **Outstanding** on **History** are $0.00. |
| **Void** | Cancelled. See [Void an invoice](#void-an-invoice). |

Kosmos makes the invoice's PDF again, and keeps that copy, when you
choose **Approved** or **Sent** and when an invoice leaves **Draft** for
any other status. So an invoice that leaves **Draft** loses the draft
mark, whichever status it goes to. Any other change, such as **Sent** to
**Deferred**, leaves the kept copy as it is.

On a **Sent** or **Deferred** invoice, **+ Card** and **+ Trust** at the
top record a payment against it. See [Payments](payments.md).

Good to know:

- Once an invoice has been emailed from Kosmos it cannot go back to
  **Draft** or **Approved**. To correct it, void it and invoice again.

## Send an invoice

1. Click **Invoices** → **Approved** and click the send button (a paper
   plane) at the right of the row. **Send Invoice** opens.
2. Check **To**, which starts as the client's email address. Separate
   several addresses with commas. Add **Cc (optional)** if you need it.
3. Edit **Message (optional)**, up to 500 characters. It starts as the
   invoice's **Message**.
4. Tick **Attach invoice PDF (always available at the pay link)** to
   attach the PDF, and click **Send**.

A message confirms the address, and the invoice becomes **Sent**. If the
email fails, the dialog says why and the status does not change.

The email comes from your firm's name followed by "Billing", for example
"Example Law Billing", with the subject "Example Law - Invoice 123". It
greets the client with "Dear Client," and carries your message, the
client's name, the invoice number and the amount due. Its **Pay now**
button opens a page where the client can download the PDF and, if your
firm takes online payments, pay. See [Payments](payments.md). Replies and
blind copies go to the **Billing Email** and **Invoice BCC** addresses on
**Settings → Firm**. See [Settings](settings.md).

After the first email, the send button offers **Resend Invoice** and
**Send Reminder**. A reminder says how long ago the invoice went out.
After that it carries the **Payment Terms** sentence that an
administrator has entered on **Settings → Firm**. Until one is entered,
the reminder states no terms. Your message goes above the reminder's own
text. A reminder does not change the status. Every attempt is kept under
**History** → **Delivery History** with its **Date**, **Type**,
**Sender**, **Recipients** and **Status** (**Sent** or **Failed**). A
**Sent** invoice emailed more than once shows the number of times beside
its status.

Good to know:

- The link in the email stops working after 90 days unless your
  administrator has set another period. Resend the invoice for a new one.
- An invoice set to **Sent** by hand has no send button. Set it back to
  **Approved** to email it.

## Void an invoice

Void an invoice that has been issued and should not stand. A Draft or
Approved invoice has no void button: delete it instead.

1. Open the invoice and click the void button (a circle with a line
   through it) at the top right. **Void Invoice** opens.
2. Type VOID in the box and click **Submit**.

The invoice is now **Void** and stays in the list with its PDF. Its
entries are unbilled again, so they return to **Work in Progress** and can
be edited. Payments and credits applied to it are taken off it and stay
on the matter, unapplied. It no longer counts in **Balance Due**. Voiding
cannot be undone, and a void invoice's status cannot be changed.

A client who opens the link from an earlier email is told "This invoice
is no longer open for payment. Please contact us if you have a question
about it."

## Delete an invoice

Anyone with the Financial permission can delete a Draft or Approved
invoice: open **Edit Invoice**, click **Delete** and confirm. Only an
administrator can delete a Void invoice, with the trash button at the top
of its page. An invoice with any other status cannot be deleted. Void it
first.

Deleting is permanent. The entries are kept and become unbilled again.
Payments and credits that were applied to the invoice are kept and become
unapplied. The record of its emails is deleted with it.

## Give a credit

A credit lowers what a client owes on a matter without a payment: a
courtesy reduction or a write-off, for example.

1. Click **Invoicing** → **Credits**, then the plus button. **Add
   Credits** opens.
2. Fill in **Date**, **Matter** and **Amount**, say why in **Detail**, and
   click **Submit**.
3. In the list, click the credit's **ID** and choose **Apply**.
4. Beside an invoice, enter the **Amount to Apply** and click **Submit**.

The credit's **Unapplied** amount falls and the invoice's **Amount Due**
falls with it. The dialog lists the matter's Sent and Deferred invoices
that still have something due, and under **Current Applications** you can
remove an application. A second amount from the same credit to the same
invoice is added to the first application. The **ID** menu also has
**Edit** and **Delete**. Removing an application, or deleting the credit,
sets an invoice it had paid off back to **Sent**.

Once a credit is applied, **Edit** will not make it smaller than the
amount applied or move it to another matter. Remove the application
first. The amount must be more than zero.

A credit lowers the matter's **Balance Due** from the day it is added. It
lowers an invoice's **Amount Due** only once it is applied. On the
matter's **Ledger** the credit is listed under its **Detail**, or as
"Credit" if you left **Detail** empty. Click it there for **Edit** and
**Delete**.

## See who owes money

**Collection** lists each billable matter with something to collect,
largest first, ten to a page. Click a matter to open its **Ledger** tab.

| Column | How it is worked out |
|---|---|
| **Billed** | The totals of the matter's Sent, Deferred and Paid invoices. |
| **Paid** | Every payment recorded on the matter, applied or not. |
| **Deferred** | The totals of the matter's Deferred invoices. |
| **Due** | **Billed** less **Paid**, credits and **Deferred**, plus anything already paid or credited toward the Deferred invoices. |

A matter is listed when **Due** is more than zero, and **Total Due After
Deferments** adds every listed matter. The tab has no ages or due dates:
use **AR Aging** in [Reports](reports.md#ar-aging) for those. You need
the Reports permission for it. Matters running low on trust are not here
either. Administrators see them under **Collections** on the dashboard.
See [Getting started](getting-started.md).

## The matter's Ledger

A matter's **Ledger** tab lists its issued invoices, payments and credits
by date with a running balance. **Balance Due** is the totals of its
Sent, Deferred and Paid invoices, less every payment and credit on the
matter, applied or not. Draft and Approved invoices appear under **Work
in Progress** instead. See [Matters](matters.md#ledger).
