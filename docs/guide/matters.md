# Matters

This page is for anyone at the firm who works on client files: attorneys,
paralegals and office staff. It covers how to find a matter, open a new
one, work in its tabs, and close it when the work is done. If you are new
to Kosmos, read [Getting started](getting-started.md) first.

## What a matter is

A matter is one piece of work for one client, for example "Rivera v.
Northside Logistics" for the client Elena Rivera. Everything about that
work hangs off the matter: the people involved, court proceedings, events,
tasks, time and expenses, invoices and payments, and the case file
(documents, notes, emails and AI chats). Each matter has one client, one
status and one billing type.

## Find a matter

Click **Matters** in the sidebar. The list shows 40 matters to a page, and
**Count** at the top right shows how many match.

| Column | What it shows |
|---|---|
| **Matter** | The matter name. Click it to open the matter. An **Admin** badge marks a matter that is not billable. |
| **Work Status** | A short note on where the matter stands. Click the text to change it, then press Enter. A matter with none shows a dash: click it to add one. |
| **Proceeding** | The case number of the matter's primary proceeding. The menu beside it has **Copy Case Number** and **View Proceedings**. |

To narrow or reorder the list:

- Click **Pending**, **Open** or **Complete** to show matters with that
  status. The list starts on **Open**, sorted by name. After that it keeps
  your filter and sort order until you change them or sign out.
- Type in **Filter list . . .** to match matter names within the current
  filter. Press Enter to open the first match.
- Click **Filter** to open **Filter Matters**. **Status** is the only
  place to choose **Closed** or **All**. **Practice area** lists your
  firm's practice areas. **Opened on or after** and **Closed on or
  before** narrow the list by date. **Ordering** sets the sort. Click
  **Apply**. **Restore Defaults** returns to open matters sorted by name.
- Click the sort button beside **Matter** or **Work Status** to sort by
  that column. Click it again to reverse the order.

## Open a new matter

1. Click **Matters** in the sidebar, then the **+** button at the left of
   the toolbar. The **Add Matter** form opens.
2. In **Client**, type part of the client's name and click the contact in
   the results. If the client is not a contact yet, see the next section.
3. Set **Status**. It starts on **Pending**.
4. Enter the **Matter Name** (50 characters at most) and check **Open
   Date**, which starts as today.
5. Fill in the other fields that apply and click **Submit**.

The form closes, and the new matter is in the list if the list is showing
its status.

| Field | Required | Notes |
|---|---|---|
| **Client** | No | Any contact. Leave it blank for an internal matter with no client. |
| **Status** | Yes | **Pending**, **Open**, **Complete** or **Closed**. |
| **Open Date** | Yes | The date the matter was opened. |
| **Matter Name** | Yes | The name shown everywhere in Kosmos. |
| **Practice Area** | No | From the firm's list. An administrator maintains it under **Settings → Practice Areas**. |
| **Description** | No | One line on what the matter is about. |
| **Work status** | No | The note shown in the **Work Status** column of the list. |
| **Jurisdiction** | No | Free text. If it is blank, the matter uses the firm's default jurisdiction. |
| **Billable** | Yes | **Yes** (the default) or **No (Administrative)**. |
| **Billing Type** | Yes | **Hourly** (the default) or **Flat Fee**. Time entries go on hourly matters. Flat fee entries go on flat fee matters. |
| **Deferred Fee Arrangement** | Yes | **No** (the default), or **Yes** when fees accrue but are not collected for now. Unbilled work on the matter is then not counted against the client's trust funds. |
| **Flat Fee Amount** | No | Appears only when **Billing Type** is **Flat Fee**. |

### Add the client while you open the matter

1. In **Client**, type the client's name. Two choices appear under the
   results: **Create new contact** and **Convert an intake…**.
2. Click **Create new contact** to open **Add Contact** with the name you
   typed. Or click **Convert an intake…** and pick the intake: its name,
   address, phone and email are copied into **Add Contact**.
3. Complete the contact and click **Submit**. (**Back** returns to the
   matter without adding a contact.)

You are back on **Add Matter** with the new contact in **Client** and
everything you had already entered still in place.

Good to know:

- A new matter is **Pending** unless you change **Status**, and the list
  starts on **Open**. Click **Pending** in the toolbar to see it.
- If you can see only assigned matters, a matter you add is assigned to
  you. See [Who can see a matter](#who-can-see-a-matter).

## The matter page

Click a matter's name in the list. The matter opens on its **Contacts**
tab. Across the top are the matter name (click it to switch to another
open matter), **Detail** and **Case**, and two buttons to add time and add
an expense (see [Time and expenses](time-and-expenses.md)). The arrows at
the far right step to the previous and next open matter. This page covers
the **Detail** side. **Case** holds the case file: documents, the
timeline, witnesses, notes, emails, AI chat and research.

### Overview

**Overview** is the summary of the matter. **Matter Detail** lists its
status, client, practice area, open date, jurisdiction and billing, and
the date it was closed once it has been. Beside
it are **Events** (upcoming events), **Tasks** (open tasks) and **Recent
Actions** (the five latest time entries). Each has a **+** button to add
one, and you can click a row to edit it. **Financials** shows **Balance
Due**, **Work in Progress** and **Trust Available**. You need the
Financial permission to see it. Ask your administrator.

### Contacts

**Contacts** lists everyone connected to the matter: the client, opposing
parties, counsel, witnesses and so on. Each has a **Group** (the side or
cluster they belong to) and a **Role** (what they are on this matter).

1. Click the **+** button. **Assign Contact** opens.
2. In **Contact**, type a name and click the contact in the results.
3. Choose a **Group** and a **Role**, then click **Assign**.

The contact appears in the table. Click its group or role to open **Edit
Assignment**: **Update** saves a change and **Remove** takes the contact
off the matter (the contact itself is kept). Click **Groups** to add a
group for this matter only, such as a set of co-defendants. An
administrator maintains the firm-wide groups and roles under **Settings →
Contacts**.

Good to know:

- The person must already be a contact. **Assign Contact** cannot create
  one.
- The client's row cannot be edited or removed here. Change the client in
  **Edit Matter**.

### Rates

**Rates** holds hourly rates that apply only to this matter, set user by
user in whole dollars. Click **Add Rate**, choose the **User**, enter the
**Matter rate** and click **Submit**. Click a rate to change or delete it.
A user with no rate here bills at their standard hourly rate, and each
user can have one rate on a matter. A matter rate fills in on new time
entries. It does not change entries already
recorded. You need the Financial permission for this tab. Ask your
administrator.

### Activity

**Activity** shows the time and expenses recorded on this matter. Switch
between **Time**, **Expenses** and **Categories**, and use **Activity
Report** to produce a report of the work. See
[Time and expenses](time-and-expenses.md).

### Events

**Events** shows this matter's hearings, deadlines and appointments as a
list or a calendar. Click the **+** button to add one. The same events
appear on the firm **Calendar**.

### Tasks

**Tasks** shows the to-do items for this matter. Click the **+** button to
add one. The same tasks appear on the firm **Tasks** page.

### Proceedings

**Proceedings** records each court case or other proceeding in the matter.
Click **Add Proceeding** and fill in **Date Filed**, **Nickname** (for
example Main or Appeal), **Forum** (the county and court), **Case
Number**, **Status** (**Ongoing**, **Concluded**, **Stayed** or
**Dismissed**) and **Primary**. Click a proceeding's nickname to edit it.
The primary proceeding's case number is the one shown in the matters list.
The first proceeding you add starts as primary. Click the circle in the
**Primary** column to make another one primary.

### Settlement

**Settlement** is a log of settlement negotiations. Click **Add Settlement
Entry** and record the **Date**, **Medium** (**Email**, **In Person**,
**Letter** or **Phone**), **Type** (**Authorization**, **Demand** or
**Offer**), **Amount** and **Notes** (50 characters at most).
Authorization entries are emphasised in the list.

### Ledger

**Ledger** is the matter's account: invoices, payments and credits with a
running balance, plus totals for **Balance Due**, **Work in Progress** and
the client's trust funds. **Download PDF** produces a copy. You need the
Financial permission for this tab. Ask your administrator.

## Who can see a matter

Most users can see every matter. An administrator can limit a user to
assigned matters only. If that is you, other matters are left out of your
matters list, the matter switcher and the matter choices in forms, and a
saved link to one shows "You don't have permission to access this page."
An administrator assigns matters under **Settings → Permissions**, from
the matters that are **Pending** or **Open**.

## Edit a matter and change its status

1. Open the matter and click **Overview**.
2. Click the pencil button beside **Matter Detail**. **Edit Matter** opens
   with the same fields as **Add Matter**.
3. Make your changes and click **Submit**.

The **Overview** shows the new details. You can also click the **Status**,
**Work Status**, **Practice Area** or **Description** value on the
**Overview** to change it there, without opening the form.

| Status | What it means in practice |
|---|---|
| **Pending** | Not yet under way. You can add tasks, events, time and expenses, but the matter is not in the matter switcher. |
| **Open** | Active work. The matter appears everywhere. |
| **Complete** | The work has ended and the file is being wound up, for example while a trust refund is outstanding. You can still record time and expenses. New task and event forms no longer offer the matter. |
| **Closed** | Final. The matter is no longer offered when you add a task, event, time entry or expense elsewhere in Kosmos. You can still add time or an expense from the matter's own page. |

## Close a matter

Set **Status** to **Complete** or **Closed**, on the **Overview** or in
**Edit Matter**. Kosmos then does the following at once, with no
confirmation:

- Records today as the matter's closing date. The **Overview** shows it
  as **Closed**.
- Marks the matter's proceedings **Concluded**, except any that are
  **Dismissed**.
- Removes the matter's links to its Gmail label and its Google Drive
  folder, so no new emails or documents arrive on the matter.

Everything already on the matter stays: documents, emails, notes, time,
invoices and the ledger. Nothing in Gmail or Google Drive is changed.

!!! note

    AI chat history on a matter is deleted once the matter has been
    **Closed** for a retention period: 180 days unless your administrator
    has set a different period or switched the deletion off. **Complete**
    does not start the period, and reopening the matter stops it.

Good to know:

- Reopening a matter clears its closing date and restores nothing else.
  Its proceedings stay **Concluded**, and the Gmail label and Drive
  folder must be linked again.

## Delete a matter

Only an administrator can delete a matter. Deleting is permanent.

1. Open **Edit Matter** from the matter's **Overview** and click
   **Delete**. The dialog counts the time entries, expense entries, tasks,
   documents, notes, events and invoices on the matter.
2. Type DELETE in the box and click **Delete Matter**.

You return to the matters list and the matter is gone. Deleted with it:
its time, expense and flat fee entries, tasks, events, documents, notes,
emails, timeline, witnesses, AI chats, research, proceedings, settlement
entries, rates, invoices, payments and credits, and its list of contacts
(the contacts themselves are kept).

Good to know:

- Trust records belong to the client and are not deleted.
