# Outgoing email

How to connect Kosmos to an SMTP server, which address each kind of mail is
sent from, and how to check that delivery works.

## Why this comes first

Signing in needs working mail. After a user enters a correct username and
password, Kosmos emails a six-digit code to the address on their account and
asks for it on the next screen. The code expires after five minutes. The
message is sent during the sign-in request itself, so if the mail server
cannot be reached the user sees a server error page instead of the code
screen. Once signed in, a session lasts eight weeks from its last request,
so users meet the code only when they sign in again.

Two consequences for a new server:

- Configure mail before you hand out accounts.
- Every user needs a real address on their account. The account made by
  `python manage.py createsuperuser` is asked for one.

## What you need

- An SMTP account with a mail provider that accepts authenticated
  submission with STARTTLS.
- One or more sender addresses on a domain you control, with whatever SPF
  and DKIM records the provider asks for. Without them, invoices and
  sign-in codes are likely to land in spam.

Every variable named below is described in the
[environment variable reference](../../reference/environment.md).

## Choose a delivery mode

`EMAIL_BACKEND` takes one of three values. Any other value stops the
application at start-up.

| Value | What happens to mail |
|---|---|
| `smtp` | Sent through the SMTP server configured below. |
| `console` | Printed to the application's standard output. Nothing is delivered. |
| `locmem` | Kept in memory. Used by the test suite; not useful on a server. |

When `EMAIL_BACKEND` is not set, the mode follows `DEBUG`: `console` when
`DEBUG` is on, `smtp` when it is off. The development template
`config/.env.dev` sets `console` explicitly, so a production file that
began as a copy of it must be changed to `smtp`.

In `console` mode you can still sign in: read the code from the output of
`python manage.py runserver`. Under the supplied gunicorn configuration,
which captures the workers' output, it is written to `logs/error.log`.

## Configure SMTP

1. In `config/.env`, set the mode and the server:

    ```
    EMAIL_BACKEND=smtp
    EMAIL_HOST=smtp.example.com
    EMAIL_PORT=587
    EMAIL_USE_TLS=True
    EMAIL_HOST_USER=kosmos@example.com
    EMAIL_HOST_PASSWORD=<the SMTP password>
    ```

2. Set the sender addresses (see the next section for which mail uses
   which):

    ```
    SERVER_EMAIL=kosmos-errors@example.com
    DEFAULT_FROM_EMAIL=office@example.com
    BILLING_FROM_EMAIL=billing@example.com
    ```

    The development template fills all three with placeholder
    `webmaster@localhost` addresses. Replace every one of them.

3. Restart the web application and the background worker. Both read
   `config/.env` only when they start.

Notes on the connection settings:

- `EMAIL_USE_TLS` means STARTTLS. Kosmos has no setting for implicit TLS
  (the mode usually offered on port 465), so use a port where the provider
  offers STARTTLS.
- Some hosting providers block outbound connections on ports 25 and 587.
  If connections time out, ask your mail provider which other ports it
  accepts (2525 is a common one) and set `EMAIL_PORT` to match.
- `EMAIL_TIMEOUT` (default 10 seconds) is how long Kosmos waits on a
  stalled connection before giving up. It exists so that a blocked port
  produces an error page at sign-in rather than a request that hangs until
  the web server kills it. Leave it low.
- With `smtp` selected and `EMAIL_HOST` empty, there is no server to
  connect to and every send fails at once, the sign-in code included.
  This is the state of a production server (`DEBUG` off) whose
  environment file has no mail settings at all.

## Which mail uses which address

There are three sender settings. `DEFAULT_FROM_EMAIL` falls back to
`SERVER_EMAIL`, and `BILLING_FROM_EMAIL` falls back to
`DEFAULT_FROM_EMAIL`, so setting only `SERVER_EMAIL` sends everything from
one address. The built-in default for `SERVER_EMAIL` is
`webmaster@localhost`, which no provider will accept: set at least that
one.

| Mail | From | Reply-To | Copies |
|---|---|---|---|
| Sign-in code | `DEFAULT_FROM_EMAIL` | none | none |
| Password reset ("Forgot Password?" on the sign-in page) | `DEFAULT_FROM_EMAIL` | none | none |
| Daily digest | `DEFAULT_FROM_EMAIL` | none | none |
| Email sent to a prospective client from an intake | the firm's name, at the address in `DEFAULT_FROM_EMAIL` | the address typed in the send dialog. It is pre-filled with the firm's Intake Email, or the firm's Email when that is blank | CC to the firm's Intake Email |
| Client intake form link and its reminder | the firm's name, at the address in `DEFAULT_FROM_EMAIL` | the firm's Email | CC as entered when sending |
| Invoice and invoice payment reminder | "*Firm* Billing", at the address in `BILLING_FROM_EMAIL` | the firm's Billing Email, or the firm's Email when that is blank | BCC to the firm's Invoice BCC list |
| Payment request, trust deposit request and their reminders | "*Firm* Billing", at the address in `BILLING_FROM_EMAIL` | the firm's Billing Email, or the firm's Email when that is blank | BCC to the firm's Invoice BCC list |
| Error reports and payment reversal notices | `SERVER_EMAIL` | none | sent to `ADMINS` |

For client-facing mail Kosmos builds the display name itself. Only the
address part of `DEFAULT_FROM_EMAIL` and `BILLING_FROM_EMAIL` is used
there, and the name comes from the firm's name in **Settings → Firm** with
a trailing entity designation removed: "Example Law, LLC" sends invoices as
"Example Law Billing" and intake mail as "Example Law". With no firm name,
the names are "Billing" and "Our office". Sign-in codes, password resets
and the digest use `DEFAULT_FROM_EMAIL` exactly as written, display name
included.

## Reply-To, BCC and the firm record

The sender addresses above are usually unattended. Where replies go is
set in the application, not in `config/.env`. An admin fills these in
under **Settings → Firm**:

| Field | Used for |
|---|---|
| Email | Reply-To on intake form mail. Fallback Reply-To for billing and intake mail. Shown as a contact address in intake form mail. |
| Billing Email | Reply-To on invoices, payment requests and reminders, and the contact address printed in those messages. |
| Invoice BCC | One or more addresses, separated by commas, that receive a blind copy of every invoice, payment request and reminder. Use it to keep the firm's own copy of exactly what each client was sent. Leave it empty to send no copies. |
| Intake Email | CC and default Reply-To on mail sent to a prospective client from an intake. |

When a field and its fallback are both empty, the message goes out with
no Reply-To header and replies go to the From address.

!!! note

    Make the Intake Email a mailbox a person reads. Do not point it at the
    address used for [intakes from forwarded
    email](inbound-email.md), or copies of the firm's own outgoing
    messages may be fed back in as new intake notes.

The firm's logo, if one is uploaded, is embedded in client-facing messages
as an inline image. It is not linked from the server, so it keeps
displaying in archived mail.

## Error mail to ADMINS

With `DEBUG` off, an unhandled error in a web request is emailed to the
people listed in `ADMINS`, from `SERVER_EMAIL`. Kosmos also uses the same
list to announce a reversed online payment or trust deposit (a returned
bank transfer, for example), because someone has to follow up with the
client.

`ADMINS` is written as a Python list of name and address pairs, quoted as
one value:

```
ADMINS="[('Ada Admin', 'ada@example.com'), ('Sam Staff', 'sam@example.com')]"
```

Take care with the syntax. Depending on the mistake, a malformed value
either stops the application at start-up or is read as an empty list, in
which case no error mail is sent and nothing tells you so. The test in
the next section catches both.

## The daily digest

The `daily-digest` job emails a summary of overdue items, today's items
and the next three days' tasks and events. It runs at 07:00 in the
server's time zone (see [Scheduled jobs](../../reference/schedules.md))
and needs the background worker to be running.

It is opt-in per user. Each user switches it on under **Settings →
Notifications**, where they can also include weekends and send themselves
a test. A user with nothing due gets no message that day. Users limited
to their assigned matters see only those matters in their digest.

## Check that it works

1. Send a plain test message. `sendtestemail` is a standard Django
   command:

    ```bash
    python manage.py sendtestemail you@example.com
    ```

    It is sent from `DEFAULT_FROM_EMAIL`. If the SMTP settings are wrong,
    the command prints the error.

2. Test the error path, which uses `SERVER_EMAIL` and `ADMINS`:

    ```bash
    python manage.py sendtestemail --admins
    ```

    Every address in `ADMINS` should receive a message.

3. Sign out and sign in again. The code should arrive within a few
   seconds.

4. Check the headers of the test message at the receiving end for SPF and
   DKIM passes. Kosmos cannot check these for you.

5. Optionally, under **Settings → Notifications**, enable the digest and
   click **Send Test**. It reports "no email sent" when you have no tasks
   or events to list, which is not a failure.

## Troubleshooting

**Sign-in shows a server error after the password is accepted.** The code
could not be sent. Run `sendtestemail` to see the SMTP error directly. A
pause of about `EMAIL_TIMEOUT` seconds before the error points to a
blocked port or a wrong host. An immediate error points to an empty
`EMAIL_HOST`, rejected credentials, or a sender address the provider
does not allow.

**The application will not start and names `EMAIL_BACKEND`.** The value
must be `console`, `locmem` or `smtp`.

**No code arrives and no error is shown.** Check that `EMAIL_BACKEND` is
not still `console`: in that mode the "message" is in the application's
output. Otherwise the provider accepted the message, so look in the
provider's logs and the recipient's spam folder.

**Invoices fail to send but sign-in codes arrive.** The provider may be
refusing `BILLING_FROM_EMAIL` as a sender. Kosmos shows the provider's
reason when the send fails and records the failed attempt in the
invoice's history.

**The digest never arrives.** Confirm the worker is running, that
`python manage.py setup_schedules` has been run, and that the user has
switched the digest on and has an address on their account.

**Clients reply to an address nobody reads.** Fill in the Email and
Billing Email fields under **Settings → Firm**.
