# Users and permissions

How to create accounts, decide what each person can reach, and take access
away again. The exact rule behind every switch is in the
[permissions matrix](../reference/permissions.md).

## Before you begin

- Outgoing email must work. Every sign-in sends a code to the user's email
  address, so an account whose mail cannot be delivered cannot sign in. The
  mail settings are in the
  [environment reference](../reference/environment.md#email).
- While `EMAIL_BACKEND=console`, nothing is delivered. The message,
  including the code, is printed to the web process log instead
  (`logs/error.log` with the gunicorn configuration in `deploy/`).
- You need shell access to the server for the first account. After that,
  everything on this page except the Django admin is done in the browser.

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

The account this creates is active, has the Admin role, and carries
Django's `is_staff` and `is_superuser` flags
([`apps/accounts/managers.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/accounts/managers.py)).
It is the only kind of account that can open the
[Django admin](#the-django-admin). Run the command again whenever you need
another one, for example after locking yourself out.

Give it a real email address you can read. You will need the emailed code
to sign in.

## How sign-in works

1. The user enters their **username** (not their email address) and
   password at `/accounts/login/`.
2. If they are correct and the account is active, Kosmos deletes any
   earlier code for that user, creates a new six-digit code, and emails it
   to the address on the account.
3. The user enters the code at `/accounts/login/verify/` and is signed in.

What to know about it:

- The code is good for five minutes. After that it is refused with "Code
  has expired. Please log in again."
- Five wrong codes in a row discard the code. The user sees "Too many
  incorrect codes. Please log in again." and starts over with the
  password, which sends a new code.
- Every sign-in asks for a code. There is no "remember this device".
- There is no resend button. To get a new code, go back to the login page
  and enter the password again. That replaces the earlier code.
- Wrong passwords are not counted, and no account is ever locked. The only
  throttle on the password step is the one nginx applies. See the
  [security checklist](security.md#tls-and-nginx).
- On a production server sign-in works only over HTTPS. See
  [Django security settings](security.md#django-security-settings).
- **Forgot Password?** on the login page emails a reset link (Django's
  standard flow; the link is good for three days). Setting a new password
  does not sign the user in. They still go through the two steps above.
- Both the code and the reset link go to the same mailbox. Anyone who
  controls a user's mailbox can therefore take over that user's Kosmos
  account. Ask users to protect their email accounts accordingly.

## Add a user

You need the Admin role.

1. Open **Settings → Users** (`/settings/users/`).
2. Click the **+** button beside the title.
3. Fill in the **Create User** form: username, password, first name, last
   name, email and role. Click **Submit**.
4. Click the new username in the list and choose **Edit** to set the rest:
   **Attorney**, **Title**, **Initials** and **Hourly Rate**.
5. Open **Settings → Permissions** and switch off anything this person
   should not have. See [Permissions](#permissions).
6. Give the user their username and password by some route other than the
   email address on the account.

Things the form does not do for you:

- It accepts a blank email address. Always enter one. Without it the user
  cannot receive a sign-in code.
- It does not test the password against the password rules. Neither does
  the user's own **Settings → Profile** password change. Only the
  **Forgot Password?** flow, `createsuperuser` and the Django admin apply
  them. Choose a strong password yourself.
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
| Django admin at `/admin/` | Only with Django's staff flag as well | No |

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
| **Reports** | Everything under `/reports/`, and the firm-wide breakdown in the dashboard's Unbilled Time section (they see their own figures instead). |
| **Research** | The Research tab in a matter's case navigation, and the research pages and actions behind it. |

The server refuses these by address (HTTP 403), not only in the menus.
Read these limits before you rely on a switch:

- **Financial** does not hide rates and amounts everywhere. The time list
  still shows its Rate and Fee columns, and the expense and flat-fee lists
  still show amounts. The Claude Desktop connection still serves a
  matter's rates, activity and settlement sections.
- **Intakes** does not cover search. Intake names still appear in
  practice-wide search results.

The [permissions matrix](../reference/permissions.md) has the full list of
what is and is not enforced, with the source location of each check.

## Limit a user to certain matters

A matter has a list of members. A user whose **All Matters** switch is off
can open only the matters they are a member of.

1. Open **Settings → Permissions** and switch **All Matters** off for the
   user.
2. Click the pencil icon that appears beside the switch (**Manage matter
   access**).
3. In the dialog, click a matter under **Open Matters** to assign it. Click
   a matter under **Assigned** to remove it. Each click saves immediately.
4. To undo the restriction, click **Grant All Matters** in the dialog, or
   switch **All Matters** back on.

The dialog lists open matters only. Creating a matter does not make its
creator a member: a restricted user who adds a matter cannot open it until
an admin assigns it to them.

For a restricted user, Kosmos then:

- leaves other matters out of the matter list, the matter switchers, and
  the matter choices in task, time, expense, document and note forms;
- answers HTTP 403 for another matter's pages under `/matters/<id>/`;
- answers HTTP 403 for anything in another matter's case workspace under
  `/case/`: its documents (including downloads and the viewer),
  highlights, timeline, witnesses, labels, notes, emails, AI chats and
  research. The check follows the record, so the address of a single
  document, chat or email is refused just as the matter's own pages are;
- leaves other matters' entries out of the time, expense and flat-fee
  lists;
- hides other matters' notes in the notes editor and in search;
- limits the dashboard's matter lists, the daily digest and the Claude
  Desktop connection to their matters.

!!! warning

    Matter membership is not a complete wall. The task list, the calendar
    and contacts are not filtered by membership, and practice-wide search
    still returns every matter, proceeding, contact and intake that
    matches. A restricted user can therefore see that another matter
    exists, its name, and the tasks and events entered for it. A user who
    also holds **Financial** or **Reports** sees every matter's invoices
    and reports. Do not use this setting as an ethical screen between
    people inside the firm.

## Settings on one user that affect others

Set these under **Settings → Users → Edit**, except where noted.

| Setting | Effect beyond the user's own screen |
|---|---|
| **Email** | Receives sign-in codes, password resets and the daily digest. Mail forwarded to the [intake address](integrations/inbound-email.md) is accepted only when it comes from an active user's email address. |
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

## The Django admin

`/admin/` is Django's built-in database administration screen. It gives
direct access to the stored records (users, matters, contacts, time and
expense entries, invoices, payments, trust transactions, documents, notes,
intakes, inbound intake email) and to the change history of many of them.
Use it for repairs that Settings has no screen for: setting another user's
password, inspecting an inbound email that did not become an intake,
correcting a record. It bypasses the application's own rules, so treat it
as a maintenance tool.

Who can reach it:

- The account must be active and have Django's staff flag. Only accounts
  made with `createsuperuser` have it. **Settings → Users** never sets it.
- The account must also have the Admin role. A signed-in user without that
  role gets HTTP 403 on every `/admin/` address.

The admin has no sign-in form of its own. `/admin/login/` redirects to
`/accounts/login/`, so a superuser signs in with the password and the
emailed code like everyone else and is then sent on to the admin. Keep the
number of superuser accounts small all the same: once inside, the admin
can change any record.

Another way to set a password without the admin, from the checkout:

```bash
.venv/bin/python manage.py changepassword <username>
```
