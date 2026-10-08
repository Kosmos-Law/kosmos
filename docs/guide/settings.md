# Settings

This page is for the person who looks after Kosmos for the firm: an office
manager or the attorney who owns the firm, signed in as an administrator.
It walks through each section under **Settings**: what it is for, what
each control does, and what changes elsewhere in Kosmos as a result. Some
sections are open to every user, and the page says which.

## Open Settings

Click your name at the foot of the sidebar and choose **Settings**. It
opens on **Profile**, with the settings menu beside it. The same account
menu shows who is signed in and holds **Log out**. The entries you see depend on your role and
permissions.

| Section | Who sees it | What it is for |
|---|---|---|
| **Profile** | Everyone | Your own name, email address, password and sidebar icon. |
| **Security** | Everyone | Your authenticator app, and signing out everywhere else. Administrators also see the firm-wide switch that requires the app. |
| **Appearance** | Everyone | Your theme and navigation layout. |
| **Firm** | Administrators | The firm's name, address, email addresses, logos and its own wording for invoices and reminders. |
| **Notifications** | Everyone | Your daily digest email. |
| **Users** | Administrators | Accounts, roles and hourly rates. |
| **Permissions** | Administrators | What each user can open. |
| **Contacts** | Administrators | The groups, roles and relationship types offered for contacts. |
| **Practice Areas** | Administrators | The practice areas offered on matters and intakes. |
| **Tasks** | Administrators, once AI is set up | How the quick task line reads what you type. |
| **Integrations** | Everyone | Google connections and AI providers. A user who is not an administrator sees only **Case Email**. |
| **Claude Desktop** | Everyone | Connecting the Claude Desktop app to Kosmos. |
| **Intake Forms** | Administrators and users with the Intakes permission | Forms sent to prospective clients. |
| **Intake Emails** | Administrators and users with the Intakes permission | Ready-made emails for intakes. |
| **Checklists** | Everyone | Checklist templates for tasks. |

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
| **Logo** | On the sign-in page, in place of the Kosmos name. At the top of invoices and the other PDFs Kosmos produces (ledgers, statements, reports). On the page where a client pays online and on intake forms. The other two logos stand in for it on their own surfaces; wherever one of them is blank, this logo shows instead. |
| **Dark-theme logo** | In place of the logo on the sign-in page, the payment page and intake forms whenever the viewer's theme is dark. Upload light-coloured artwork on a transparent background: the logo itself, if it is dark ink on a transparent background, disappears on a dark theme. |
| **Email logo** | In invoice, payment request, reminder and intake form emails. An email program can be in dark mode too, and Kosmos cannot tell, so upload artwork on a solid white background, which reads in either. |
| **Name** | At the top of the same PDFs, and as the sender's name on email to clients: "Example Law Billing" on invoices and payment requests, "Example Law" on intake email. An ending such as "LLC" is left off the sender's name. |
| **Address line 1**, **Address line 2**, **City**, **State**, **Zip code** | Under the firm's name on PDFs, and at the foot of invoice, payment request and intake form emails. |
| **Phone** | On PDFs and in intake form emails. Enter a ten-digit US number. |
| **Email** | On PDFs and intake forms. Replies to intake form emails go here. It also stands in when **Billing Email** or **Intake Email** is blank. |
| **Billing Email** | Where a client's reply to an invoice, payment request or reminder goes, and the contact address printed in those emails. |
| **Invoice BCC** | One or more addresses, separated by commas. Each gets a blind copy of every invoice, payment request and reminder email. |
| **Intake Email** | Copied on every email you send to a prospective client from an intake, and filled in as **Reply-To** when you write one. |
| **Jurisdiction** | The firm's default jurisdiction. A matter with no jurisdiction of its own shows "Firm Default" with this value on its **Overview**, and AI chat on that matter works from it. |
| **Payment Terms** | One sentence in the firm's own words, for example the payment terms in your fee agreement. It is added to the reminder emails for an invoice and for a payment request (not for a trust deposit request). Leave it blank and reminders say nothing about terms. |
| **Invoice Trust Note** | Printed under **Funds in Trust** on an invoice, when the client has money in trust. Leave it blank and the invoice shows the balance alone. |

To add a logo, click the file chooser beside its name and pick a PNG or
JPG file of 2 MB or less. It uploads at once: there is nothing to save. To
change it, click the remove button beside the logo, confirm, and choose
the new file. Each preview sits on the background its logo is meant for,
light or dark, whatever your own theme, so you can see how it will read.

One logo is enough to start: upload the **Logo** alone and it shows
everywhere. Add the other two when the one logo does not suit a dark
theme or a dark email program.

## Security

**Settings → Security** is where you set up an authenticator app, so that
the second step of your sign-in is the code the app shows rather than a
code sent by email. Click **Set up an authenticator app**, scan the QR
code with the app (or type the key shown beneath it into the app), enter
the six-digit code the app shows and click **Confirm**. From your next
sign-in Kosmos asks for the app's code and sends no email.

Once an app is set up the page offers **Set up a new app**, for a new
phone (the old app stops working when the new one is confirmed), and
**Turn off**, which asks for a current code from the app and returns you
to emailed codes. When the firm requires the app, **Turn off** is not
offered. If you lose your phone, an administrator resets your app from
**Settings → Users**; you get an emailed code at your next sign-in and
set the app up again.

An administrator also sees a **Firm** section on this page with
**Require Authenticator App**. Click **Require** and every user must sign
in with an app: a user who has not set one up is brought to this page
after signing in and can go nowhere else until they have, and nobody can
turn their app off. **Stop Requiring** lets each user choose again and
removes nobody's app.

**Sign Out Everywhere** is further down the page. Click **Sign Out
Everywhere Else** and every other device and browser signed in to your
account is signed out at once (a lost phone, a shared computer); you stay
signed in where you clicked it. **Log out** in the account menu, by
contrast, signs out the browser you are using and no other. A browser you
do not sign out of stays signed in for eight weeks after you last use it.

## Users

**Settings → Users** opens **User Management**, the list of accounts, ten
to a page. Click a **Username** for **Edit**, **Switch to Inactive** and,
for a user with an authenticator app, **Reset Authenticator**; or click a
**Role** to change it. The **Attorney** column shows the user's
title and, where there is none, "Attorney" or "Staff". The **App** column
shows a check for each user who has set up an authenticator app. The list starts
with active users only: click **Filter** to narrow it by username, email,
role or status (**Not Active** or **All** shows deactivated users), then
**Apply**. **Restore Defaults** returns to active users. Click the sort
button beside **Username**, **E-Mail**, **Role**, **Attorney**, **Rate** or
**Active** to sort by that column, and again to reverse the order. Sorting
keeps the filter in place.

### Add a user

1. Click the **+** button beside **User Management** to open **Create
   User**.
2. Enter **Username** (a short display name), **Password**, **First
   name**, **Last name** and **Email address**, and choose a **Role**.
   The email address is what the user signs in with: it is required, and
   no two users can share one.
3. Click **Submit**.

The new user is in the list. Kosmos sends them nothing: give them the
password yourself. Each time they sign in, Kosmos emails a code to their
email address, until they set up an authenticator app under **Settings →
Security**. Next, edit the user to fill in the remaining fields, and
check their row under [Permissions](#permissions).

### Edit a user

Click the username, then **Edit**. Change the fields in **Edit User** and
click **Submit**.

| Field | What it does |
|---|---|
| **Username** | A short display name, shown on tasks, entries and reports. It does not sign in. |
| **Email address** | What the user signs in with. Also receives sign-in codes, password reset links and the daily digest. No two users can share one. |
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

### Reset an authenticator app

When a user loses the phone with their authenticator app, click their
username and choose **Reset Authenticator**, then confirm. They get a code
by email at their next sign-in. If the firm requires the app, Kosmos then
takes them to **Settings → Security** to set a new one up before they can
do anything else.

Good to know:

- A new user starts with every permission switched on except
  **Reports**. Set their permissions before you hand over the password.
- **Create User** accepts a blank **Email address**, but a user with none
  cannot receive a sign-in code and so cannot sign in.
- Kosmos does not let the firm be left without an administrator. If you
  try to make the only active administrator a **User** or **Inactive**,
  yourself included, it shows "This is the only active administrator.
  Make another user an administrator first."

## Permissions

**Settings → Permissions** has a row for each active user and a switch
for each permission. A switch applies from the next page the user opens.
An administrator's row is marked "admin": its switches are on and locked.

| Permission | What it opens |
|---|---|
| **All Matters** | Every matter. Switched off, the user sees only the matters assigned to them. |
| **Financial** | **Invoicing** (invoices, payments and trust), the **Rates** and **Ledger** tabs of a matter, the **Financials** figures on a matter's **Overview**, and the **Trust** tab of a client's contact page. |
| **Intakes** | The **Intakes** page, and **Intake Forms** and **Intake Emails** in Settings. |
| **Reports** | The **Reports** page, and the whole firm's figures under **Work in Progress** on the Dash. This switch starts off for a new user. The other four start on. |
| **Research** | A matter's saved case law (the **Case Law** view of its **AI** tab, or a **Case Law** tab of its own when AI is not set up), and case law search in an Agentic chat. |

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

- Assigned matters do not limit the money pages. A user with the
  Financial permission still sees every matter's invoices, payments and
  trust under **Invoicing**, and a user with the Reports permission sees
  every matter in the reports.
- Contacts belong to the whole firm. A user limited to assigned matters
  still sees every contact, though not the other matters a contact is
  on. The operator guide has the full list:
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
typed into it, for everyone at the firm. The page appears in the menu
only once an AI provider is set up (see [AI](#ai)). Without one, the
quick-add line always reads "Matter - Description".

| Field | What it does |
|---|---|
| **AI Quick Task Entry** | **No**: type the matter, a dash and the task ("Rivera - Draft the complaint"), and Kosmos matches the matter by name. **Yes**: describe the task in plain language, and AI works out the matter, the assignee, the date and the priority. |
| **Quick Task AI Model** | **Gemini Flash** or **Claude Sonnet**. Used only when **AI Quick Task Entry** is **Yes**. |

Click **Save Task Settings**. If the AI cannot be reached, the line falls
back to matching "Matter - Description". If the provider of the model you
pick has no key, Kosmos uses the other provider's model.

## Integrations

**Settings → Integrations** connects Kosmos to Google and to the AI
providers. An administrator sees **Google Account**, three connections
that serve the whole firm through one Google account, **AI** and **Case
Email**. Everyone else sees only **Case Email**.

| Connection | What it does once connected |
|---|---|
| **Google Contacts** | A contact added in Kosmos is added to the Google account, and removed from it when the contact is deleted in Kosmos. |
| **Google Calendar** | Events are kept in step, in both directions, with one Google calendar. The person who runs your server chooses which. |
| **Google Drive (Documents)** | PDFs in a matter's linked Drive folder are copied into the matter's documents. Kosmos never changes anything in Drive. The lines under the button count the matters linked, folders mapped and documents synced, and warn when a mapped folder is missing. |

To connect one, click **Connect**, choose the Google account and approve
the request. You return to **Integrations** and the button now reads
**Disconnect**. If you see "This Google connection was not started from
this session. Go back to Settings, Integrations and connect again.",
click **Connect** again.

If Google sign-in is not set up on your server yet, there are no
**Connect** buttons. An administrator sees a note pointing to the setup
guide ([Google Workspace](../admin/integrations/google.md)). Everyone else
sees "Google sign-in isn't set up yet. Ask an administrator."

To disconnect one, click **Disconnect**, then **Disconnect** again in the
prompt. Kosmos stops syncing with it for the whole firm until an
administrator connects it again. Documents and events already in Kosmos
stay in place.

Under **Case Email**, each user connects their own Gmail mailbox: click
**Connect** beside **Your Gmail mailbox**. Kosmos creates the case labels
in that mailbox, and emails you put under a label appear on that matter's
**Emails** tab. The section then shows your mailbox's address, how many
emails are synced, when your mailbox last synced, and how many labels it
is missing. The missing labels are named only if you can see every
matter. An administrator sees these lines for every connected mailbox,
not only their own. **Reconnect** appears for a mailbox that was
connected before Kosmos could create labels. **Disconnect** asks you to
confirm, then removes that mailbox's emails from matters. Emails a
colleague's mailbox also holds, and emails already saved as documents,
are kept.

Good to know:

- Whichever **Connect** you click, Google asks for access to calendar,
  contacts, Drive and Gmail together. Kosmos uses only the connection you
  clicked.
- Connecting with a different Google account replaces the earlier
  connection.

### AI

AI in Kosmos is optional. Until a provider is set up, Kosmos shows no AI
anywhere: no **AI** tab on matters, no **Assessment** or **Chat** on
intakes, no **AI** column on documents, and no **Settings → Tasks**.
Setting one up turns all of them on for everyone at the firm.

**AI** has a row for **Google Gemini** and one for **Anthropic Claude**.
One is enough. Either provider runs every AI feature. With both, chats
offer the models of both, and the work Kosmos does in the background
(summaries, intake assessments, reading forwarded email) uses Gemini.
Search by meaning inside a matter needs Gemini. Without it, search
matches your words only.

To set one up:

1. Create an API key in the firm's account with Google or Anthropic.
2. Paste it into **API key** on that provider's row and click **Save**.

Kosmos checks the key with the provider before it saves it. If the
provider refuses it, the row reads "The provider rejected this key. Check
it and try again." and nothing is saved. A saved key shows **Remove** in
place of the box. Click **Remove** and confirm to delete it. If it was
the only key, the AI features disappear again.

A row that reads "Set in config/.env" has a key set by the person who
runs your server. It cannot be changed here. What is sent to each
provider, and the cost, are described in
[AI providers and research](../admin/integrations/ai.md).

!!! note

    Sending email, file storage, CourtListener and online payments have no
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
