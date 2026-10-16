# Intakes from forwarded email (Mailgun)

Forward a prospective client's email (or a voicemail transcription email)
to an intake address such as `kosmos-intakes@mail.example.com`. Mailgun
POSTs the parsed message to `/api/inbound-email/`; the app verifies the
signature, checks the sender, and a worker task asks the AI to extract
intake fields. The result is a new Open intake whose first note holds the
original message text. If extraction fails, the intake is still created
from the raw message and the stored `InboundEmail` row records the error
(visible in the Django admin).

Without an AI key ([AI providers](ai.md#without-an-ai-key)) the address
still works: the intake is created from the raw message, named after the
subject, with no extracted fields, no AI summary and no assessment, and
the row is `processed`, not `failed`. Follow-ups are not matched, since
matching uses the extracted email and phone.

Follow-ups work the same way (with AI): forward them to the same address. When the
extracted sender email (or, failing that, a 10-digit phone match) matches
an existing intake, the message is logged as a note on that intake instead
of opening a duplicate; the most recent matching intake wins. A follow-up
landing on an Unresponsive intake flips it back to Open (the caller
resurfacing is what that status was waiting on); every other status is
left alone.

Only mail sent FROM an active firm user's login email is accepted; anything
else (spam sent straight to the intake address) is dropped without a trace.
Forward from the same address that is on your Kosmos user account, or the
message will be silently ignored.

## One-time setup

The examples use `mail.example.com` as the Mailgun domain and
`kosmos.example.com` as the Kosmos host. Substitute your own.

1. **DNS.** Add Mailgun's MX records on the Mailgun domain. Using a
   subdomain keeps this separate from the mail for your main domain:

   ```
   mail.example.com.  MX 10 mxa.mailgun.org.
   mail.example.com.  MX 10 mxb.mailgun.org.
   ```

2. **Route.** Create a Mailgun route that forwards the intake address to
   the webhook:

   - Expression: `match_recipient("kosmos-intakes@mail\.example\.com")`
   - Actions: `forward("https://kosmos.example.com/api/inbound-email/")`,
     `stop()`

   The route can be created through the API if the dashboard form gives
   trouble:

   ```
   curl -s --user 'api:<MAILGUN_API_KEY>' https://api.mailgun.net/v3/routes \
     -F priority=0 \
     -F description='Intake forwards to Kosmos' \
     -F expression='match_recipient("kosmos-intakes@mail\.example\.com")' \
     -F action='forward("https://kosmos.example.com/api/inbound-email/")' \
     -F action='stop()'
   ```

3. **Recipient.** The local part of the intake address (the part before
   the `@`) must match `INTAKE_INBOUND_RECIPIENT` in `config/.env`. The
   default is `kosmos-intakes`. Mail delivered to the webhook for any other
   address is dropped.

4. **Signing key.** Mailgun dashboard > Settings > API Security > HTTP
   webhook signing key. Put it in `config/.env`:

   ```
   MAILGUN_WEBHOOK_SIGNING_KEY=key-...
   ```

   While the variable is empty the webhook refuses every request, so
   forwarded mail is dropped until the key is set.

5. Restart gunicorn and the qcluster worker.

## Sharing one route between instances

Some Mailgun plans allow only one route. A single route can serve several
addresses and several Kosmos instances (for example production and a test
server), because each instance only processes mail for the address it
owns:

- Expression:
  `match_recipient("(kosmos-intakes|kosmos-test-intakes)@mail\.example\.com")`
- Actions: one `forward(...)` per instance webhook, then `stop()`

Every matched message goes to every webhook. Set
`INTAKE_INBOUND_RECIPIENT=kosmos-intakes` on one instance and
`kosmos-test-intakes` on the other, and each drops the mail that is not
its own.

## Smoke test

Forward any email from a firm user's address to the intake address. An
Open intake with a first note ("Email In" or "VM In") should appear in the
intakes list within a minute. If nothing appears, check the `InboundEmail`
rows in the admin: no row means the message was rejected at the webhook
(signature, sender or recipient); a `failed` row means the AI call failed
but a fallback intake should still be linked.

## Calendar invitations

The same route and webhook can carry the firm's calendar address,
`calendar@mail.example.com`. Set it in `config/.env`:

```
CALENDAR_INBOUND_ADDRESS=calendar@mail.example.com
```

and add its local part to the route's expression, for example
`match_recipient("(kosmos-intakes|calendar)@mail\.example\.com")`.
While the variable is empty, both uses below are off.

- **Forwarding in.** A firm user forwards a calendar invitation (the
  email with its `.ics` attachment) to the address from their Kosmos login
  email. It is posted as a firm event, with no assignees and no matter;
  anyone can then set its assignees in Edit Event. The invitation's join
  link (from its `CONFERENCE`, `X-GOOGLE-CONFERENCE` or Teams property, or
  else the first Zoom, Teams, Meet or Webex link in its location or text)
  is the event's meeting link, its text is the event's details, and its
  `ORGANIZER` is shown on the event. A location that is only the link or
  the service's name ("Microsoft Teams Meeting") is dropped. A later
  revision of the same invitation updates the event, a cancellation
  removes it, and the user gets a short email saying what happened.
- **Inviting guests.** The Edit Event dialog has a Guests section for
  people outside the firm. Each is emailed an invitation their calendar
  app can answer, with the meeting link as `CONFERENCE` and `URL` (and as
  the location when there is no place), and the link and details as its
  text; the address is its organiser, so the answers come back here, show
  against the guest, and are emailed to whoever invited them. A
  change to the event goes out again; deleting it, or removing a guest,
  sends a cancellation. An address that belongs to a firm user, or is on
  the firm's own email domain (Settings > Firm), is refused with a pointer
  to the event's assignees.

Like the intake address, the sender check reads the message's From
header, which can be forged. Each calendar-address message logs the SPF,
DKIM and DMARC results Mailgun reports.
