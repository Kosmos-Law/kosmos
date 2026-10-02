# Settings

This page is for the person who looks after Kosmos for the firm: an office
manager or the attorney who owns the firm, signed in as an administrator.
It walks through each section under **Settings**: what it is for, what
each control does, and what changes elsewhere in Kosmos as a result. Some
sections are open to every user, and the page says which.

## Open Settings

Click **Settings** in the sidebar. It opens on **Session**, with the
settings menu beside it. The entries you see depend on your role and
permissions.

| Section | Who sees it | What it is for |
|---|---|---|
| **Profile** | Everyone | Your own name, email address and password. |
| **Appearance** | Everyone | Your theme and navigation layout. |
| **Firm** | Administrators | The firm's name, address, email addresses and logo. |
| **Notifications** | Everyone | Your daily digest email. |
| **Session** | Everyone | Signing out. |
| **Users** | Administrators | Accounts, roles and hourly rates. |
| **Permissions** | Administrators | What each user can open. |
| **Contacts** | Administrators | The groups, roles and relationship types offered for contacts. |
| **Practice Areas** | Administrators | The practice areas offered on matters and intakes. |
| **Tasks** | Administrators | How the quick task line reads what you type. |
| **Integrations** | Everyone | Google connections. A user who is not an administrator sees only **Case Email**. |
| **Claude Desktop** | Everyone | Connecting the Claude Desktop app to Kosmos. |
| **Intake Forms** | Administrators and users with the Intakes permission | Forms sent to prospective clients. |
| **Intake Emails** | Administrators and users with the Intakes permission | Ready-made emails for intakes. |
| **Checklists** | Administrators and users with the Financial permission | Checklist templates for tasks. |

## Your own settings

**Profile**, **Appearance** and **Notifications** belong to each user and
change nothing for anyone else. See
[Make it yours](getting-started.md#make-it-yours).

## Firm

**Settings → Firm** holds the details Kosmos prints and sends in the
firm's name. Change the fields and click **Save Firm Details**. "Firm
details updated" confirms the save.

| Field | Where it shows up |
|---|---|
| **Logo** | On the sign-in page, in place of the Kosmos name. At the top of invoices and the other PDFs Kosmos produces (ledgers, statements, reports). In invoice, payment request and intake form emails, on the page where a client pays online, and on intake forms. |
| **Name** | At the top of the same PDFs, and as the sender's name on email to clients: "Example Law Billing" on invoices and payment requests, "Example Law" on intake email. An ending such as "LLC" is left off the sender's name. |
| **Address line 1**, **Address line 2**, **City**, **State**, **Zip code** | Under the firm's name on PDFs, and at the foot of invoice, payment request and intake form emails. |
| **Phone** | On PDFs and in intake form emails. Enter a ten-digit US number. |
| **Email** | On PDFs and intake forms. Replies to intake form emails go here. It also stands in when **Billing Email** or **Intake Email** is blank. |
| **Billing Email** | Where a client's reply to an invoice, payment request or reminder goes, and the contact address printed in those emails. |
| **Invoice BCC** | One or more addresses, separated by commas. Each gets a blind copy of every invoice, payment request and reminder email. |
| **Intake Email** | Copied on every email you send to a prospective client from an intake, and filled in as **Reply-To** when you write one. |
| **Jurisdiction** | The firm's default jurisdiction. A matter with no jurisdiction of its own shows "Firm Default" with this value on its **Overview**, and AI chat on that matter works from it. |

To add the logo, click the file chooser beside **Logo** and pick a PNG or
JPG file of 2 MB or less. It uploads at once: there is nothing to save. To
change it, click the remove button beside the logo, confirm, and choose
the new file.

## Session

**Settings → Session** shows **Logged in as** with your username. Click
**Logout** to sign out of Kosmos in this browser. You are returned to the
sign-in page, and other browsers and devices stay signed in. A browser you
do not sign out of stays signed in for eight weeks after you last use it.

## Users

**Settings → Users** opens **User Management**, the list of accounts, ten
to a page. Click a **Username** for **Edit** and **Switch to Inactive**,
or a **Role** to change it. The **Attorney** column shows the user's
title and, where there is none, "Attorney" or "Staff". The list starts
with active users only: click **Filter** to narrow it by username, email,
role or status (**Not Active** or **All** shows deactivated users), then
**Apply**. **Restore Defaults** returns to active users.

### Add a user

1. Click the **+** button beside **User Management** to open **Create
   User**.
2. Enter **Username**, **Password**, **First name**, **Last name** and
   **Email address**, and choose a **Role**.
3. Click **Submit**.

The new user is in the list. Kosmos sends them nothing: give them the
username and password yourself. Each time they sign in, Kosmos emails a
code to their email address. Next, edit the user to fill in the remaining
fields, and check their row under [Permissions](#permissions).

### Edit a user

Click the username, then **Edit**. Change the fields in **Edit User** and
click **Submit**.

| Field | What it does |
|---|---|
| **Username** | The name the user signs in with. |
| **Email address** | Receives sign-in codes, password reset links and the daily digest. |
| **First name**, **Last name** | Shown wherever the user is named. |
| **Role** | **Admin**: every settings section, every matter and all five permissions, and the only role that can delete a matter. **User**: day-to-day work within the permissions and matters an administrator gives them. You can also change it from the **Role** column of the list. It applies from the next page the user opens. |
| **Attorney** | **Yes** or **No**. With no **Title**, the user is described as "Attorney" or "Staff". |
| **Title** | A job title, such as Paralegal. Printed beside the user on a matter's activity reports and given to the AI so it knows who is who. |
| **Initials** | How the user is abbreviated in lists of time and expenses, on task filter chips and on reports. |
| **Hourly Rate** | In whole dollars. Fills in as the rate on the user's new time entries, unless the matter has its own rate for them. See [Rates](matters.md#rates). |
| **Status** | **Active** or **Inactive**. |

### Deactivate a user

A user cannot be deleted. Click the username and choose **Switch to
Inactive** (or set **Status** to **Inactive** in **Edit User**). The user
is signed out everywhere and can no longer sign in. They leave the
**Permissions** table and are no longer offered when a task is assigned.
Everything they recorded stays. To bring the account back, click
**Filter**, choose **Not Active**, click the username and choose **Switch
to Active**. Their permissions and assigned matters return as they were.

### Passwords

An administrator cannot see or reset another user's password here. A user
changes their own under **Settings → Profile**, or clicks **Forgot
Password?** on the sign-in page and follows the link Kosmos emails them.
If their email address is wrong, correct it in **Edit User** first.

Good to know:

- A new user starts with all five permissions switched on. Set their
  permissions before you hand over the password.
- **Create User** accepts a blank **Email address**, but a user with none
  cannot receive a sign-in code and so cannot sign in.
- Nothing stops you from changing your own role to **User** or
  deactivating your own account. If no administrator is left, the person
  who runs your server has to create one: see
  [Users and permissions](../admin/users.md).

## Permissions

**Settings → Permissions** has a row for each active user and a switch
for each permission. A switch applies from the next page the user opens.
An administrator's row is marked "admin": its switches are on and locked.

| Permission | What it opens |
|---|---|
| **All Matters** | Every matter. Switched off, the user sees only the matters assigned to them. |
| **Financial** | **Invoicing** (invoices, payments and trust), the **Rates** and **Ledger** tabs of a matter, and the **Financials** figures on a matter's **Overview**. |
| **Intakes** | The **Intakes** page, and **Intake Forms** and **Intake Emails** in Settings. |
| **Reports** | The **Reports** page. |
| **Research** | The **Research** tab in a matter's case file. |

### Limit a user to assigned matters

1. Switch **All Matters** off for the user. A pencil button appears beside
   the switch.
2. Click the pencil button. **Matter Access** opens with two lists:
   **Pending and Open Matters** and **Assigned**.
3. Click a matter under **Pending and Open Matters** to assign it, or one
   under **Assigned** to take it away. Each click is saved at once. Click
   **Accept & Close** when you are done.

The user now sees only the matters under **Assigned**.
[Who can see a matter](matters.md#who-can-see-a-matter) describes what
that looks like for them. To lift the limit, click **Grant All Matters**
in the dialog or switch **All Matters** back on.

Good to know:

- Assigned matters are not a complete wall. The **Tasks** page, the
  **Calendar** and **Contacts** still show entries for other matters, and
  a user with the Financial or Reports permission still sees every
  matter's invoices and reports. The operator guide has the full list:
  [Users and permissions](../admin/users.md).

## Contacts

**Settings → Contacts** holds three lists the firm chooses from when it
works with [contacts](contacts.md).

| List | What its entries are | Where they are offered |
|---|---|---|
| **Groups** | The side or cluster a contact belongs to on a matter. | **Group**, when you assign a contact to a matter. They are offered in the order shown here: drag a row by its handle to reorder. |
| **Roles** | What a contact is on a matter. | **Role**, when you assign a contact to a matter. |
| **Relationship Types** | How two contacts are connected, read from both sides: **Label** ("Employer of") and **Inverse label** ("Employee of"). Leave **Inverse label** blank when both sides read the same, as with a spouse. | **Relationship**, when you link one contact to another. |

Each list shows active entries until you click **Inactive** or **All**.

- **Add**: click the **+** button beside the list's title, fill in the
  form and click **Submit**.
- **Rename**: click the entry, choose **Edit** and change the name. Every
  record that uses the entry shows the new name.
- **Retire**: in **Edit**, set **Status** to **Inactive**. The entry is
  no longer offered, and records that already use it keep it.
- **Delete**: click the entry, choose **Delete** and confirm.

The group and the role Kosmos uses for a matter's client show
**Protected** in place of **Edit** and **Delete**.

Good to know:

- Deleting reaches the records that use the entry. Deleting a group or a
  role takes every contact assigned with it off their matters. Deleting a
  relationship type removes every link of that type between contacts. The
  contacts themselves are kept. To keep the records, retire the entry.

## Practice Areas

**Settings → Practice Areas** is the list offered in **Practice Area**
when you add or edit a [matter](matters.md) or an [intake](intakes.md).
It works like the lists under **Contacts**, except that its form has a
**Name** and an **Is active** checkbox. Clear **Is active** to retire a
practice area: it is no longer offered, and matters and intakes that have
it keep it. **Delete** removes it from every matter and intake that uses
it, leaving them with none.

## Tasks

**Settings → Tasks** has one section, **Quick Task Entry**. It sets how
the quick-add line at the top of the [Tasks](tasks.md) page reads what is
typed into it, for everyone at the firm.

| Field | What it does |
|---|---|
| **AI Quick Task Entry** | **No**: type the matter, a dash and the task ("Rivera - Draft the complaint"), and Kosmos matches the matter by name. **Yes**: describe the task in plain language, and AI works out the matter, the assignee, the date and the priority. |
| **Quick Task AI Model** | **Gemini Flash** or **Claude Sonnet**. Used only when **AI Quick Task Entry** is **Yes**. |

Click **Save Task Settings**. If the AI cannot be reached, the line falls
back to matching "Matter - Description". The model you pick works only if
the person who runs your server has set up that AI provider: see
[AI providers](../admin/integrations/ai.md).

## Integrations

**Settings → Integrations** connects Kosmos to Google. An administrator
sees **Google Account**, three connections that serve the whole firm
through one Google account, and **Case Email**. Everyone else sees only
**Case Email**.

| Connection | What it does once connected |
|---|---|
| **Google Contacts** | A contact added in Kosmos is added to the Google account, and removed from it when the contact is deleted in Kosmos. |
| **Google Calendar** | Events are kept in step, in both directions, with one Google calendar. The person who runs your server chooses which. |
| **Google Drive (Documents)** | PDFs in a matter's linked Drive folder are copied into the matter's documents. Kosmos never changes anything in Drive. The lines under the button count the matters linked, folders mapped and documents synced, and warn when a mapped folder is missing. |

To connect one, click **Connect**, choose the Google account and approve
the request. You return to **Integrations** and the button now reads
**Disconnect**. Disconnecting leaves documents and events already in
Kosmos in place.

Under **Case Email**, each user connects their own Gmail mailbox: click
**Connect** beside **Your Gmail mailbox**. Kosmos creates the case labels
in that mailbox, and emails you put under a label appear on that matter's
**Emails** tab. The section then shows your mailbox's address, how many
emails are synced, when each connected mailbox last synced, and any
labels a mailbox is missing. **Reconnect** appears for a mailbox that was
connected before Kosmos could create labels. **Disconnect** removes that
mailbox's emails from matters. Emails a colleague's mailbox also holds,
and emails already saved as documents, are kept.

Good to know:

- Whichever **Connect** you click, Google asks for access to calendar,
  contacts, Drive and Gmail together. Kosmos uses only the connection you
  clicked.
- **Disconnect** beside the three firm-wide connections acts at once,
  with no confirmation. Connecting with a different Google account
  replaces the earlier connection.

!!! note

    Sending email, file storage, AI providers and online payments have no
    screen in Settings. The person who runs your server sets them up, along
    with the Google project behind these connections: see
    [Google](../admin/integrations/google.md) and
    [Gmail](../admin/integrations/gmail.md) in the operator guide.

## Claude Desktop

**Settings → Claude Desktop** lets each user connect the Claude Desktop
app on their own computer to Kosmos. The page states exactly what Claude
can then read and write: in short, the matters that user can see.

Click **Generate token**, then follow the four steps under **Setup**:
they include downloading a small connector file and pasting your
configuration into Claude Desktop. The configuration contains your
personal token, so do not share it. **Rotate token** replaces the token,
and Claude Desktop stops working until you paste the new configuration.
**Revoke token** removes it. Both also cut off the LibreOffice companion
extension, which uses the same token. More detail is in
[Claude Desktop access](../admin/integrations/claude-desktop.md).

## Intake Forms

**Settings → Intake Forms** lists the forms the firm sends to prospective
clients, with how many **Questions** each has and how many times it has
been **Sent**. Click **New Form** to build one, or a form's name to change
it. [Intakes](intakes.md) covers building and sending forms.

## Intake Emails

**Settings → Intake Emails** is the firm's set of ready-made emails for
prospective clients: a rejection, a referral, a request for information.
When you choose **Send email** on an [intake](intakes.md), **Template**
lists them by name, and picking one fills in **Subject** and **Body**,
which you can still edit before sending.

Click the **+** button beside **Intake Emails** to open **Add Email
Template**. Enter a **Name** (how it appears under **Template**), a
**Subject** and the **Body**, and click **Submit**. Click a template's
name for **Edit** and **Delete**. The body is plain text and is sent as
written: Kosmos does not fill in names, so add the greeting when you
send. Changing or deleting a template does not touch emails already sent.

## Checklists

**Settings → Checklists** is the firm's library of checklist templates:
reusable lists of steps to attach to a task. Templates are kept in
**Folders**, and **Inbox** holds those not yet filed. Click the **+**
button above the list to add one, or a template's name for **Edit**,
**Move** and **Delete**. Deleting a template does not change checklists
already on tasks. See [Tasks](tasks.md).
