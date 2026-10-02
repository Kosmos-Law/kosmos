# Time and expenses

This page is for anyone who records work so it can be billed: attorneys,
paralegals and office staff. It covers the three kinds of entry, how to
record, find and change them, and what happens to an entry once it is on
an invoice.

## The three kinds of entry

| Entry | What it records | Matters it can go on |
|---|---|---|
| Time | Hours worked, at an hourly rate | Matters whose **Billing Type** is Hourly |
| Expense | A cost, as a dollar amount | Any matter |
| Flat fee | A fixed fee, as a dollar amount | Matters whose **Billing Type** is Flat Fee |

**Activity** in the sidebar lists entries across matters on three tabs:
**Time**, **Expenses** and **Flat Fees**. A matter's **Activity** tab
(see [Matters](matters.md)) lists that matter's entries under **Time** and
**Expenses** and adds a **Categories** view. Flat fees are not listed
there. Every entry is saved under the person who is signed in. There is no
field for recording work on behalf of someone else.

## Record time

1. Click **Activity** in the sidebar. The **Time** tab opens.
2. Click the plus button at the left of the toolbar. **Add Time Entry**
   opens.
3. Choose the **Matter**. The list holds hourly matters that are Pending,
   Open or Complete. **Rate** fills in when you choose.
4. Type what you did in **Actions** and enter the **Hours**. Check the
   **Date**, which starts as today.
5. Click **Submit**.

The form closes and the list refreshes. Every field is required except
**Comp** and **Entered**, which start at **No**.

| Field | Notes |
|---|---|
| **Matter** | Below it, **Trust Available (Pending)** shows the client's trust money left after what is owed and unbilled. |
| **Hours** | Tenths of an hour: 0.1 is six minutes. Starts at 0.2. The largest value is 99.9. |
| **Comp** | **Yes** records the work without charging for it. The list shows "comp" in place of the rate and fee. |
| **Entered** | **Yes** keeps the entry out of **Work in Progress**, and a new invoice does not pick it up. Leave it at **No** for work to be billed from Kosmos. |

You can also click the clock button (**Add time**) in a matter's header.
After **Submit**, Kosmos takes you to **Activity** → **Time**. Or press
Space then `n` on any page and choose **Time Entry**.

Good to know:

- Kosmos does not round hours and sets no minimum. It accepts one decimal
  place only, so 0.25 is refused.
- The **Time** tab opens on your own entries for today. An entry with
  another date is saved but does not appear until you change the date.

### How the rate is chosen

When you choose a matter, Kosmos fills in **Rate**, in whole dollars an
hour. You can type over it. It uses, in this order:

1. The rate set for you on that matter's **Rates** tab, if there is one.
2. Otherwise, the **Hourly Rate** on your user account.

To set a matter rate, open the matter's **Rates** tab, click **Add Rate**,
choose the **User**, enter the **Matter rate** and click **Submit**. You
need the Financial permission to see the **Rates** tab. Your own **Hourly
Rate** is set by an administrator under **Settings → Users**. The rate is
saved on each entry, so a later change does not alter entries already
saved.

## Use abbreviations

Your firm can define short codes that expand into full phrases in the
**Actions** box. Suppose the firm has the code `tcw` for "telephone
conference with".

1. In **Actions**, type `tcw Elena Rivera re deposition dates`.
2. Read the **Preview:** line that appears under the box. It shows
   "telephone conference with Elena Rivera re deposition dates".
3. Leave the checkbox beside the preview ticked and click **Submit**.
   Untick it to save the text exactly as you typed it.

The list shows the expanded text. To see the codes, click **View
Abbreviation Codes** at the bottom of the form, or the code button at the
right of the **Time** toolbar, which opens the searchable **Abbreviation
Codes** list. Administrators also get a plus button there to add a code
(**Abbreviation Code**, **Expansion Text**, **Submit**), and can click a
code for **Edit** or **Delete**.

Good to know:

- Codes are case-sensitive, and Kosmos replaces a code wherever those
  characters appear, including inside a longer word. Check the preview.
- The form opened from a matter's header shows the preview but has no
  checkbox, and it saves the text as typed, without expanding it.

## Record an expense

1. Click **Activity** → **Expenses**, then the plus button. **Add Expense
   Entry** opens.
2. Choose the **Matter** (any matter that is Pending, Open or Complete)
   and fill in **Date**, **Description** and **Amount**. All four are
   required.
3. Optionally choose a **Category**: Contract Services, Court Reporters,
   Filing Fee, Outside Counsel, Postage or Process Server. This fixed list
   is not the matter category described below.
4. Set **Comp** and **Entered** as for time, then click **Submit**.

The list shows the category in front of the description. Unlike time, an
expense is one amount with no hours or rate, and abbreviation codes do not
apply. The receipt button (**Add expense**) in a matter's header and Space
then `n` → **Expense** open the same form.

Good to know:

- When you add an expense, Kosmos replaces `ff`, `fx` and `ml`, each
  followed by a space, with "Filing fee", "FedEx" and "Mail". It does this
  inside words too: "staff meeting" becomes "staFiling fee meeting". Read
  the description in the list after you save.
- The largest amount an expense can hold is $9,999.99.

## Record a flat fee

1. Click **Activity** → **Flat Fees**, then the plus button. **Add
   Flat-Fee Entry** opens.
2. Choose the **Matter**. Only flat-fee matters are listed. **Amount**
   fills in from the matter's **Flat Fee Amount**, if one is set.
3. Fill in **Date** and **Description**, check **Amount**, and click
   **Submit**.

A flat fee has no hours, rate, category or abbreviation codes, and there
is no button for it in a matter's header.

## File entries under categories

Categories belong to one matter. They sort its time and expenses into
groups, and the groups marked **Claimed** become the sections of the
matter's fee claim report. An entry has one category or none.

1. Open the matter, click the **Activity** tab, then **Categories**.
2. Click the plus button beside the **Category** heading. Enter a **Name**,
   set **Claimed**, and click **Submit**. Drag rows to reorder them. Click
   a name for **Edit** or **Delete**.
3. Click **Time** or **Expenses**. In the **Category** column, click the
   entry's category (or the icon, when it has none) and choose one.
   **None** clears it.

The entry now shows the category, and the **Categories** view adds it to
that category's totals. To list one category's entries, use the **All
Categories** button on the **Time** or **Expenses** view. Deleting a
category leaves its entries uncategorized. Categories cannot be set in the
entry forms or in the sidebar's **Activity** lists, and flat fees have
none.

## Find and review entries

**Time** opens on your own entries for today. **Expenses** and **Flat
Fees** open on everyone's entries that are not Entered and not on an
invoice, although the date button reads **All Dates**. Each list shows ten
entries a page, newest first.

**Time** has the columns Date, User, Matter, Actions, Hours, Rate and Fee.
**Expenses** and **Flat Fees** have Date, User, Matter, Description and
Amount. **User** shows initials, and a matter name opens that matter's
**Activity** tab. To narrow or reorder a list:

- **Date button.** Choose **All Dates**, **Today**, **Yesterday**, **This
  Week**, **Last Week**, **This Month**, **Last Month** or **Work in
  Progress**. Weeks start on Monday. **Flat Fees** has no **Last Week** or
  **Last Month**. **Work in Progress** shows unbilled entries of any date.
- **User chips.** Click **All** or a person's initials. In a firm of more
  than five people, a three-dot button lists everyone and lets you pin up
  to five as chips. Press `[` or `]` to step through users.
- **Filter.** Set **Date** (a range), **User**, **Matter**, **Client**
  (not on **Expenses**), **Keyword**, **Comp**, **Entered**, **Invoice**
  and **Ordering**, then click **Apply**. **Restore Defaults** returns the
  list to how it opens.
- **Sort arrows.** Click the arrows beside **Date**, **Matter**, or
  **Actions** or **Description**. Click again to reverse.

Totals under the list cover every entry that matches, not only the page
you are on: **Total Hours**, **Comp Hours** and **Net Hours** and the same
three for fees on **Time**, and total, comp and net amounts on the other
tabs. An extra row, such as **Admin Hours**, appears when entries sit on a
non-billable matter. Net leaves out comp and admin.

To export, click the download button at the right of the toolbar, choose
**Standard** or **Clio** (**Flat Fees** has one format), and confirm with
**Download**. You get a spreadsheet (CSV) file of every entry that matches
the current filters.

- **Standard** for time holds Date, Matter, User, Actions, Hours, Rate,
  Fee, Comp, Discounted Fee, Entered and Invoice. For expenses and flat
  fees it holds Date, Matter, User, Description, Amount, Comp, Discounted
  Amount, Entered and Invoice.
- **Clio** is laid out for import into Clio. It leaves out entries on
  matters that have no **Clio Matter** set.

For a PDF, open the matter's **Activity** tab and click **Activity
Report**. **All Activity** downloads the matter's timekeepers, time, flat
fees, expenses and total. **Fee Claim** opens **Fee and Expense Report**:
set its options and click **Download PDF**.

## Edit, delete or change several entries

1. Click the entry's text in the **Actions** or **Description** column.
2. Change the fields and click **Submit**. To remove the entry, click
   **Delete** and confirm.

The list refreshes with the change. To change several entries at once:

1. Tick the box at the left of each entry. The box in the heading selects
   the whole page.
2. In the toolbar, click **Matter** and choose a matter to move the
   entries to, or click **Comp** and choose **Comp** or **Not Comp**.

The selection clears and the list refreshes. To cancel instead, click the
count at the left of the toolbar. In the sidebar's **Activity** lists you
need the Financial permission for the tick boxes. Ask your administrator.
A matter's **Time** list has them for everyone and adds **Category**.

Good to know:

- On **Expenses** and **Flat Fees**, clicking the **Amount** of an entry
  that is not on an invoice flips its **Entered** setting. Nothing asks
  you to confirm, and the entry can drop out of the list.
- Moving an entry to another matter, singly or in bulk, takes it off any
  draft invoice.
- In bulk changes on **Time** and **Expenses**, entries on an invoice that
  is past Draft are skipped, and a message says how many. **Flat Fees**
  does not skip them.

## What happens once an entry is billed

An entry is unbilled when **Entered** is **No** and it is on no invoice.
That is what **Work in Progress** lists. On **Time**, it also leaves out
non-billable matters.

- When an invoice is created for a matter, Kosmos puts the matter's
  unbilled entries dated up to the invoice's **Limit Date** on it.
- While the invoice is a draft, the entry is gone from **Work in
  Progress** but you can still edit or delete it.
- Once the invoice is approved, the entry's text in the list is no longer
  a link, so you cannot open it to edit or delete it. That plain text is
  the only sign in the list that an entry is billed.
- If the invoice is voided, its entries become unbilled again.

Good to know:

- Two places still open a billed entry for editing: the **Expenses** list
  on a matter's **Activity** tab, and **Recent Actions** on a matter's
  **Overview**. Kosmos does not stop the change.
- You can still change the category of a billed entry.

## Who sees what

- If you are limited to assigned matters, the lists and their totals hold
  only those matters' entries. The **Matter** list in a form can still
  offer other matters, but picking one gives an error under **Matter**.
- **Rate**, **Fee** and **Amount**, and the totals, are shown to everyone
  who can see an entry. The Financial permission does not hide them.
- Without the Financial permission, you do not get the tick boxes or the
  **Matter** and **Comp** menus in the sidebar's **Activity** lists, or a
  matter's **Rates** tab.
- Only administrators can add, edit or delete abbreviation codes. See
  [Users and permissions](../admin/users.md#permissions).
