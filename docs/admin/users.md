# Users and permissions

How to create accounts, decide what each person can reach, and take access
away again. The exact rule behind every switch is in the
[permissions matrix](../reference/permissions.md).

## Before you begin

- Outgoing email must work. A sign-in sends a code to the user's email
  address unless they have set up an authenticator app, so an account
  whose mail cannot be delivered cannot sign in until it has. The mail
  settings are in the
  [environment reference](../reference/environment.md#email).
- While `EMAIL_BACKEND=console`, nothing is delivered. The message,
  including the code, is printed to the web process log instead
  (`logs/error.log` with the gunicorn configuration in `deploy/`).
- You need shell access to the server for the first account. After that,
  everything on this page is done in the browser, except the two
  command-line repairs noted where they apply.

## Create the first administrator

The installer does this for you. `scripts/install.sh` runs
`createsuperuser` and prompts for a username, email address and password,
unless a superuser already exists, you passed `--no-superuser`, or there is
no terminal to prompt on. To create it without a prompt, export
`DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL` and
`DJANGO_SUPERUSER_PASSWORD` before running the installer.

To do it by hand, from the checkout:

```bash
.venv/bin/python manage.py createsuperuser
```

The account this creates is active and has the Admin role
([`apps/accounts/managers.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/accounts/managers.py)).
It also carries Django's `is_staff` and `is_superuser` flags, which
nothing in Kosmos reads. Run the command again whenever you need another
administrator, for example after locking yourself out.

Give it a real email address you can read: it is what the user signs in
with, and the first sign-in's code goes there.

## How sign-in works

1. The user enters their **email address** and password at
   `/accounts/login/`. Case does not matter in the address. The username
   is a display name and does not sign in.
2. If they are correct and the account is active, the second step depends
   on the user:
    - **With an authenticator app set up**, the user enters the code the
      app shows at `/accounts/login/authenticator/`. No email is sent.
    - **Without one**, Kosmos deletes any earlier code for that user,
      creates a new six-digit code, emails it to the address on the
      account, and the user enters it at `/accounts/login/verify/`.
3. The user is signed in.

What to know about it:

- The emailed code is good for five minutes. After that it is refused
  with "Code has expired. Please log in again."
- Five wrong emailed codes in a row discard the code. The user sees "Too
  many incorrect codes. Please log in again." and starts over with the
  password, which sends a new code.
- Every sign-in asks for a code. There is no "remember this device".
- There is no resend button. To get a new emailed code, go back to the
  login page and enter the password again. That replaces the earlier code.
- An app code is accepted once. The same code cannot sign in twice, even
  within its 30 seconds. A phone whose clock is up to 30 seconds out still
  signs in.
- A user with an app cannot fall back to the emailed code. If the phone
  is lost, see [Reset a user's authenticator app](#reset-a-users-authenticator-app).
- **Repeated failures start a cooldown.** Kosmos counts wrong passwords
  and wrong app codes per email address as typed, whether or not the
  address belongs to anyone. The first five failures are free. The fifth
  starts a 30-second wait, and each further failure doubles it, up to 15
  minutes. During the wait the sign-in page answers "Too many failed
  sign-ins. Try again in N minutes." without checking the password. A
  completed sign-in clears the count, and so does an hour without a
  failure. There is no permanent lock, and nothing to unlock. The nginx
  limit in the [security checklist](security.md#tls-and-nginx) applies on
  top of this.
- On a production server sign-in works only over HTTPS. See
  [Django security settings](security.md#django-security-settings).
- **Forgot Password?** on the login page emails a reset link (Django's
  standard flow; the link is good for three days). Setting a new password
  does not sign the user in. They still go through the two steps above.
- For a user without an app, both the code and the reset link go to the
  same mailbox. Anyone who controls that mailbox can take over the user's
  Kosmos account. Ask users to protect their email accounts, or require
  the app (below).

## The authenticator app

Any app that shows time-based six-digit codes (TOTP) works: Google
Authenticator, Microsoft Authenticator, Authy, 1Password and the like.

Each user sets up their own under **Settings → Security**: click **Set up
an authenticator app**, scan the QR code (or type the key shown under it
into the app), then enter the code the app shows and click **Confirm**.
From the next sign-in the app's code replaces the emailed one. The same
page has **Set up a new app** (for a new phone; the old app stops working
once the new one is confirmed) and **Turn off**, which asks for a current
code and returns the user to emailed codes.

To make the app compulsory for the whole firm, open **Settings →
Security** as an administrator and click **Require** beside **Require
Authenticator App** (the **Firm** section of that page, shown to
administrators only). From then on:

- A user who signs in without one is taken to **Settings → Security** and
  can open nothing else (the menu still shows; every other page sends
  them back) until they have set an app up. Sign out still works.
- **Turn off** disappears from the Security page, and the server refuses
  the request behind it.
- Users who already had an app notice nothing.

**Stop Requiring** lets each user choose again. Nobody's app is removed.

The **App** column of **Settings → Users** shows a check for each user
with an app set up.

### Reset a user's authenticator app

When a user loses the phone, an administrator opens **Settings → Users**,
clicks the username and chooses **Reset Authenticator**. The entry is only
offered for a user who has an app. The user gets an emailed code at their
next sign-in and, if the firm requires the app, is taken to the Security
page to set a new one up.

If the person locked out is the only administrator, reset it from the
checkout instead:

```bash
.venv/bin/python manage.py reset_authenticator <email>
```

The app's secret is stored in the database as it is, like the password
hashes. It does not depend on `SECRET_KEY`, so changing that key, or
restoring the database on another machine, keeps every enrolment. Guard
database backups accordingly; see
[File permissions](security.md#file-permissions).

## Add a user

You need the Admin role.

1. Open **Settings → Users** (`/settings/users/`).
2. Click the **+** button beside the title.
3. Fill in the **Create User** form: username (a short display name),
   password, first name, last name, email and role. Click **Submit**. The
   email address is what the user signs in with, so it is required and
   no two users may share one.
4. Click the new username in the list and choose **Edit** to set the rest:
   **Attorney**, **Title**, **Initials** and **Hourly Rate**.
5. Open **Settings → Permissions** and switch off anything this person
   should not have. See [Permissions](#permissions).
6. Give the user their password by some route other than the email
   address on the account.

Things the form does not do for you:

- It does not test the password against the password rules. Neither does
  the user's own **Settings → Profile** password change. Only the
  **Forgot Password?** flow and `createsuperuser` apply them. Choose a
  strong password yourself.
- **A new user starts with all five permissions switched on.** Do step 5
  before you hand over the password.

To check it worked, sign out and sign in as the new user, or ask them to.

## Roles

There are two roles. To change one, click the role in the **Role** column
of **Settings → Users** and pick **User** or **Admin**. The change applies
from the user's next request.

| | Admin | User |
|---|---|---|
| Permission switches | All treated as on, and locked on in the matrix | Whatever the five switches say |
| Matters | All | All, or only assigned ones. See below |
| **Settings → Users**, **Permissions**, **Firm**, **Contacts**, **Practice Areas** and **Tasks** | Yes | No (hidden from the menu, and HTTP 403 by address) |
| Delete a matter | Yes | No |
| Delete a voided invoice | Yes | No |
| Add, edit or delete time-entry abbreviation codes | Yes | No |
| Connect or disconnect the firm's Google Calendar, Contacts and Drive | Yes | No. Any user can connect their own Gmail mailbox |
| Dashboard "Collections" section | Yes | No |
| Reset another user's authenticator app | Yes | No |

A few menu entries are hidden from some users without the server refusing
the address behind them. The matrix lists each one under
[Navigation gates](../reference/permissions.md#navigation-gates).

!!! warning

    Nothing stops you from changing your own role to User, or from
    deactivating the only admin. If that happens, create a new
    administrator from the shell with `createsuperuser`.

## Permissions

**Settings → Permissions** (`/settings/permissions/`) shows one row for each
active user and five switches. A switch takes effect on the user's next
request. Admin rows are shown switched on and cannot be changed.

| Switch | When it is off, the user loses |
|---|---|
| **All Matters** | Access to matters they are not assigned to. See [Limit a user to certain matters](#limit-a-user-to-certain-matters). |
| **Financial** | Everything under `/invoicing/` (invoices, unbilled work, payments, credits, payment requests, the trust ledger), the Rates and Ledger tabs of a matter, the balance and trust figures on a matter's Overview, bulk "change matter" and "comp" on time and expense lists, and the ledger, trust and invoice reads in the [Claude Desktop](integrations/claude-desktop.md) connection. |
| **Intakes** | Everything under `/intakes/`, including the intake form builder, and the intake email templates under **Settings → Intake Emails**. |
| **Reports** | Everything under `/reports/`, and the firm-wide breakdown in the dashboard's Work in Progress section (they see their own figures instead). This switch starts off for a new user; the other four start on. |
| **Research** | A matter's saved case law (the **Case Law** view of the AI tab), the case-law viewer, and the Agentic chat's case law search and its saving of cases to the matter. |

The server refuses these by address (HTTP 403), not only in the menus.
Read these limits before you rely on a switch:

- **Financial** does not hide rates and amounts everywhere. The time list
  still shows its Rate and Fee columns, and the expense and flat-fee lists
  still show amounts. The Claude Desktop connection still serves a
  matter's rates, activity and settlement sections.

The [permissions matrix](../reference/permissions.md) has the full list of
what is and is not enforced, with the source location of each check.

## Limit a user to certain matters

A matter has a list of members. A user whose **All Matters** switch is off
can open only the matters they are a member of.

1. Open **Settings → Permissions** and switch **All Matters** off for the
   user.
2. Click the pencil icon that appears beside the switch (**Manage matter
   access**).
3. In the dialog, click a matter under **Pending and Open Matters** to
   assign it. Click a matter under **Assigned** to remove it. Each click
   saves immediately.
4. To undo the restriction, click **Grant All Matters** in the dialog, or
   switch **All Matters** back on.

The dialog lists pending and open matters only. A restricted user who
adds a matter is made a member of it, so they can open what they create.

For a restricted user, Kosmos then:

- leaves other matters out of the matter list, the matter switchers, and
  the matter choices in task, event, time, expense, document and note
  forms;
- leaves other matters' tasks and events out of the task list and board,
  the calendar and the daily digest (tasks and events on no matter stay),
  and refuses one that is asked for directly;
- lists only their matters on a contact's page, and refuses to assign a
  contact to, or remove one from, another matter;
- answers HTTP 403 for another matter's pages under `/matters/<id>/`;
- answers HTTP 403 for anything in another matter's case workspace under
  `/case/`: its documents (including downloads and the viewer),
  highlights, timeline, witnesses, labels, notes, emails, AI chats and
  research. The check follows the record, so the address of a single
  document, chat or email is refused just as the matter's own pages are;
- leaves other matters' entries out of the time, expense and flat-fee
  lists and their CSV exports, and refuses another matter's entry when
  it is asked for directly;
- leaves other matters, their proceedings and their notes out of search,
  and hides their notes in the notes editor;
- limits the dashboard's matter lists and upcoming events, the daily
  digest and the Claude Desktop connection to their matters.

!!! warning

    Matter membership is not a complete wall. Contacts are firm-wide: a
    restricted user can open any contact, including another matter's
    client. A user who also holds **Financial** or **Reports** sees every
    matter's invoices and reports. Do not use this setting as an ethical
    screen between people inside the firm.

## Settings on one user that affect others

Set these under **Settings → Users → Edit**, except where noted.

| Setting | Effect beyond the user's own screen |
|---|---|
| **Email** | The address the user signs in with. Receives sign-in codes, password resets and the daily digest. Mail forwarded to the [intake address](integrations/inbound-email.md) is accepted only when it comes from an active user's email address. |
| **Attorney** and **Title** | The title is printed beside the user on a matter's activity report and fee and expense report, and is given to the AI as part of the firm roster. With no title, the user is described as "Attorney" when **Attorney** is Yes and "Staff" when it is No. |
| **Hourly Rate** | Whole dollars. Used as the rate on the user's time entries unless the matter has its own rate for that user. |
| **Initials** | Shown wherever the user is abbreviated, for example on task filter chips. |
| **Daily digest** | Each user switches this on for themselves under **Settings → Notifications**. It is off by default, and an admin cannot set it for someone else. The [`daily-digest` job](../reference/schedules.md) sends it. |

## How long a session lasts

A session lasts 56 days from the user's last request. Each request renews
it, so someone who uses Kosmos at least once every eight weeks stays signed
in on that browser. Both values (`SESSION_COOKIE_AGE` and
`SESSION_SAVE_EVERY_REQUEST`) are fixed in
[`config/settings.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/config/settings.py)
and cannot be set from `config/.env`.

To end one user's sessions on every device, deactivate the account or
change its password.

## Deactivate a user

There is no delete. An account is switched off and its records stay.

1. Open **Settings → Users**.
2. Click the username and choose **Switch to Inactive**. (Editing the user
   and setting **Status** to Inactive does the same.)

From the user's next request:

- Sign-in is refused, and existing sessions stop working.
- The user's API token is rejected with HTTP 401. That is the token used by
  Claude Desktop and by the LibreOffice companion extension. The token is
  not deleted: if you reactivate the account, the same token works again.
- Mail they forward to the intake address is dropped.
- They no longer receive the daily digest, and they disappear from the
  permissions matrix and from user pickers.

What deactivating does not do:

- It does not disconnect a Gmail mailbox the user connected. Synchronizing
  continues. Only the user can disconnect it (**Settings → Integrations**),
  so have them do that first.
- It does not remove their matter assignments or permission switches. They
  come back as they were if the account is reactivated.

The user list shows active users only. To see the others, click **Filter**
and change the status. You may find an inactive user named `kosmos` there:
it is the system identity that signs notes created from forwarded intake
email. It has no usable password. Leave it inactive.

To check it worked, try to sign in as the user.

## Repairs from the command line

There is no Django admin site: it was removed so that every change to a
record goes through the application's own screens, where its rules apply.
Two repairs that Settings has no screen for are done from the checkout:

```bash
.venv/bin/python manage.py changepassword <username>
.venv/bin/python manage.py reset_authenticator <email>
```

`changepassword` takes the username (the display name), not the email
address. For anything else, `manage.py shell` reaches every record, with
no rules applied: treat it as a last resort.
