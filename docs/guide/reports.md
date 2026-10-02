# Reports

This page is for attorneys and office managers who want to see how the
firm is doing: hours worked, money received, fees collected, unbilled
time, new intakes, clients and unpaid invoices. It covers what each report
shows and how each figure is arrived at, so you can check it against your
own books.

## Open Reports

Click **Reports** in the sidebar. It opens on **Revenue**. The tabs across
the top are **Activity**, **Revenue**, **Realization**, **Work in
Progress**, **Intakes**, **Clients** and **AR Aging**. You need the
Reports permission for this. Ask your administrator.

Without the permission, **Reports** is not in your sidebar. You still see
your own work in progress on the Dash. See
[Getting started](getting-started.md#start-the-day-on-the-dash).

Every report is a screen to read. None has an export, download or print
button. To get entries as a spreadsheet, use the download button in
**Activity** in the sidebar. See [Time and expenses](time-and-expenses.md).

Good to know:

- Reports cover every matter in the firm. If you are limited to assigned
  matters, you still see the names and figures of the others here.
- Reports do not check the Financial permission. Anyone who can open them
  sees payments, invoices and balances.
- If **Reports** is in your sidebar but the reports do not open, your
  account lacks a setting that is not on the **Settings** pages. Ask your
  administrator, who can read [Users and permissions](../admin/users.md).

## Choose the months

**Activity**, **Revenue**, **Realization** and **Intakes** each show six
months side by side. The label between the two arrow buttons names the
last of the six, for example "Oct 2026".

1. Click the left arrow to move the six months back by one month.
2. Click the right arrow to move forward again.

The chart and the table redraw. The right arrow stops at the current
month (on **Realization**, at the last complete month). Each report
remembers its own months until you sign out. In the month headings, the
first column and each January also show the year.

## Activity

**Activity** answers: how many hours did each person record each month,
and what were they worth?

The chart has one stacked bar for each month, with the month's total
above it. The table has a **User** column, a column for each month, and
**Total**. Each cell shows the hours, the number of entries and the fees.
There is a row for each active user who recorded time on a billable
matter in the six months, in order of first name, one **Inactive** row
for all deactivated users together, and a **Total** row.

How the figures are arrived at:

- Only time entries count. Expenses and flat fees are not here.
- An entry belongs to the month of its **Date**, the day the work was
  done.
- Fees are hours times the rate on the entry.
- Comp entries count in full, in both hours and fees.
- It makes no difference whether the entry is billed, unbilled or marked
  **Entered**.
- Time on non-billable (Admin) matters is left out.

The buttons above the chart change the chart only:

- **By User** or **By Matter**. **By Matter** shows the four matters with
  the most hours over the six months, and **Other** for the rest.
- **Fees** or **Hours**.

The chart starts on **By User** and **Fees**.

## Revenue

**Revenue** answers: how much money came in each month, and whose work
did it pay for?

The chart stacks each month's payments by person, with **Unassigned** and
a grey **Other (expenses, flat fees, unapplied)**. The table has a
**User** column, a column for each month, and **Total**. Each cell shows
dollars and that row's share of the month. The rows are the people, in
order of name, then **Expenses**, **Flat fees**, **Unassigned** and
**Unapplied**. A row with nothing in the six months is not shown. The
**Total** row is all the payments dated in each month.

How the figures are arrived at:

1. Kosmos takes every payment recorded on a matter, by any method, and
   puts it in the month of the payment's date. The date of the work and
   the date of the invoice play no part.
2. The part of a payment applied to an invoice is split across that
   invoice's time, expenses and flat fees in proportion to their amounts.
   Comp items get nothing.
3. The share for time goes to the person who recorded it. The share for
   expenses goes to **Expenses**, and for flat fees to **Flat fees**.
4. Any part of a payment not applied to an invoice goes to **Unapplied**.
5. Money applied to an invoice with nothing chargeable on it goes to
   **Unassigned**.

Credits are not payments and are not counted. The only control is the
pair of month arrows.

## Realization

**Realization** answers: of the fees worked in each month, how much has
been collected, and where does the rest stand?

Above the chart, **Realization rate:** gives the rate for the six months
together. The chart has one stacked bar for each month, with that month's
rate above it. The table has a **Disposition** column, a column for each
month, and **Total**. Each cell shows a share of the month's fees and the
dollars. Below are **Accrued fees**, **Realized (collected)** and
**Realization rate (hourly)**.

The report starts from time entries on billable matters, at hours times
rate, in the month of the work. It then places every dollar in one row:

| Row | What is in it |
|---|---|
| **Collected** | The entry's share of the payments applied to its invoice. |
| **Credits applied** | The entry's share of the credits applied to its invoice. |
| **Outstanding** | The entry's share of what is still unpaid on its invoice. This includes an invoice that is a draft, or approved and not yet sent. |
| **Deferred** | The unpaid share, when the invoice's status is Deferred. |
| **Uncollectible** | The unpaid share, when the invoice's status is Uncollectible. |
| **Write-downs (comp & discount)** | Comp time at its full value, the entry's share of any discount on its invoice, and comp flat fees. |
| **Unbilled (WIP)** | Time that is on no invoice, including time marked **Entered**. |
| **Flat fees** | Flat fee entries dated in the month, at their full amount, whether or not they are billed or paid. |

An entry's share is its amount divided by the invoice's total before
discount (time, expenses and flat fees, leaving out comp). Expenses are
not in this report, so the part of a payment that covers expenses appears
nowhere here.

- **Accrued fees** is the sum of all the rows.
- **Realized (collected)** repeats the **Collected** row.
- **Realization rate (hourly)** is **Collected** divided by **Accrued
  fees** less the **Flat fees** row.

The only control is the pair of month arrows.

Good to know:

- Months are months of work, not of payment. A payment received today
  for work done in March raises March, so past months keep changing.
- **Collected** here is not the **Revenue** total. Revenue counts all
  money by the date it arrived. **Collected** counts only money for time,
  by the date the time was worked.

## Work in Progress

**Work in Progress** answers: how much recorded time is waiting to go on
an invoice right now?

There are two sections, **WIP by User** and **WIP by Matter**. Each has a
ring chart with the total in the middle and a table with the columns
**User** or **Matter**, **Hours**, **Gross**, **Comp**, **Net** and **% of
net**, ending in a **Total** row. Rows run from the largest **Net** down.
Click a matter's name to open it. The matter chart shows the eight
largest matters and **Other**.

How the figures are arrived at:

- Only time entries count, on billable matters, of any date.
- An entry counts when **Entered** is **No** and it is on no invoice.
  Time on a draft invoice has left this report.
- **Gross** is hours times rate for all those entries. **Comp** is the
  part of that from comp entries. **Net** is **Gross** less **Comp**.
- **Hours** include comp hours.

Click **Gross** or **Net** above a chart to change what that chart
measures. It starts on **Net**. There is no date control: the report is
the position at this moment.

## Intakes

**Intakes** answers: how many intakes arrived each month, of what kind,
and how many became clients? For intakes themselves, see
[Intakes](intakes.md).

At the top is a line chart of the number of intakes each month. Below it
are two ring charts: **Outcomes**, with the share converted beside the
heading, and **Practice Areas**. Then come two tables. **Outcomes by
Month** has the columns **Month**, **Open**, **Pending**, **Accepted**,
**Referred Out**, **Client Declined**, **Unresponsive** and **Total**.
**Practice Area by Month** has **Month**, a column for each practice area
and **Total**. Each cell shows a count and its share of the month.

How the figures are arrived at:

- An intake belongs to the month of its date. An intake with no date is
  left out.
- The status counted is the intake's status now, not its status in that
  month.
- The share converted is the **Accepted** intakes divided by all intakes
  in the six months.
- In **Practice Areas**, an intake with no practice area is counted as
  **Unspecified**.

The only control is the pair of month arrows.

Good to know:

- **Practice Area by Month** has a fixed set of columns, which is not
  your firm's list under **Settings → Practice Areas**. An intake whose
  practice area is not one of the columns, or that has none, is missing
  from that table and its totals. The **Practice Areas** chart counts
  every intake.
- The last row of **Outcomes by Month** takes its **Total** and its
  percentages from the practice area table, so they can be wrong. Add up
  the status columns instead.

## Clients

**Clients** answers: for each current client, how much work, billing and
payment was there in the recent period?

The ring chart shows **Billed**: the seven clients with the largest
**Invoices** figure, and **All others**. The table has the columns
**Client**, **Hours**, **Fees**, **Invoices** and **Payments**. **Hours**
also shows the number of entries, and **Invoices** and **Payments** show
how many there were. There is no total row.

How the figures are arrived at:

- There is a row for every contact who is the client on at least one
  matter that is Open or Complete, even when every figure is zero. The
  figures cover all of that client's matters, whatever their status.
- **Hours** and **Fees** are the time entries dated in the period, at
  hours times rate. Comp entries count in full, and so does time on
  non-billable (Admin) matters.
- **Invoices** is the total of invoices issued in the period whose status
  is Sent or Paid, after comp and discount. Draft, Approved, Deferred,
  Uncollectible and Void invoices are left out.
- **Payments** is the payments dated in the period.

To change the period, click the date button and choose **1 Month**, **3
Months**, **6 Months** or **12 Months**. The report starts on **3
Months**. The period counts back from today, so it is not a set of
calendar months. Click the arrows beside a column heading to sort by that
column, and again to reverse. Click a client's name to open the contact
(see [Contacts](contacts.md)).

## AR Aging

**AR Aging** answers: who owes the firm money, and how old is each unpaid
invoice?

The chart shows the total owed in each age band. The table has the
columns **Client / Invoice**, **Matter**, **Date Issued**, **Days**,
**Current**, **31-60**, **61-90**, **91-120**, **120+** and **Total**.
There is one line for each invoice, grouped under its client. The first
column shows the client's name only. A client's **Total** is on the
right, and the **Total** row at the bottom adds up each band.

How the figures are arrived at:

- An invoice is listed when its status is Sent and something is still
  owed on it. Draft, Approved, Deferred, Uncollectible, Paid and Void
  invoices are not listed.
- The amount is the invoice total, after comp and discount, less the
  payments and credits applied to it.
- **Days** counts from **Date Issued** to today. No due date is used.
  **Current** means 30 days or fewer.

Click the arrows beside **Client / Invoice** to sort by client name, or
beside **Total** to sort by amount owed. Click a matter's name to open
the matter. There is no date control: the report is the position today.

## When two figures disagree

Several words appear in more than one place with different meanings.

| Words | Where | What is counted |
|---|---|---|
| **Fees** | **Activity** | Time on billable matters, comp included. |
| **Fees** | **Clients** | Time on all matters, Admin matters and comp included. |
| **Work in Progress** | This report and the Dash | Time only, on billable matters, not **Entered** and on no invoice. |
| **Work in Progress** | A matter's **Overview** and **Ledger** | Time, expenses and flat fees, less comp, including work on draft and approved invoices. |
| **Unbilled (WIP)** | **Realization** | Time on no invoice, including **Entered** time. Comp is in write-downs. |
| **Outstanding** | **Realization** | Unpaid time, including on draft and approved invoices. |
| Amounts owed | **AR Aging** | Time, expenses and flat fees on Sent invoices only. |

## Reports on one matter

A matter's **Activity** tab has its own **Activity Report**, which
produces a PDF of that matter's work or a **Fee and Expense Report** for
a fee claim. See [Time and expenses](time-and-expenses.md).
