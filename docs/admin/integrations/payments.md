# Online payments

Kosmos can collect money through a payment processor. Three kinds of email
carry a link to a public payment page that needs no login:

- **Invoice emails and invoice reminders** link to `/pay/<token>/`, where
  the client pays the invoice's remaining balance.
- **Payment requests** link to `/pay/balance/<token>/`, where the client
  pays an amount staff chose, up to the matter's open balance. The payment
  is applied to the matter's open invoices, oldest first.
- **Trust deposit requests** use the same URL shape. The client pays an
  amount staff chose and Kosmos records a deposit in that client's trust
  ledger.

Card and bank details are typed into fields served by the processor. They
never reach the Kosmos server. Kosmos receives a one-time token, asks the
processor to charge it, and records the result.

The `PAYMENT_PROCESSOR` variable in `config/.env` selects the processor.
The default is `fake`, which simulates payments and needs no credentials.

!!! warning

    There is no setting that removes the pay link from invoice emails.
    While `PAYMENT_PROCESSOR=fake`, a client who opens the link sees a
    simulation form, and submitting it records a payment and marks the
    invoice paid although no money moved. Configure a real processor
    before the instance sends invoices to real clients.

## Before you start

You need:

- A running Kosmos instance with **both** the web service and the
  background worker (`qcluster`). Settlement is handled by the worker. See
  [Running background tasks](../install-manual.md#running-background-tasks).
- A public HTTPS hostname. Clients must be able to open `/pay/...` and the
  processor must be able to POST to `/webhooks/...` from the internet,
  without logging in. The examples use `kosmos.example.com`.
- Working outbound email, and at least one address in `ADMINS`. Kosmos
  emails `ADMINS` when an accepted payment later fails or is returned.
- A merchant account with one of the supported processors, and its API
  credentials. Start with sandbox or test credentials.

Every variable named on this page is described in the
[environment variable reference](../../reference/environment.md#billing-and-payments).
This page only says which ones each step needs.

The web service and the worker each read `config/.env` once, when they
start. After any change to it, restart both. With the bundled systemd
units:

```bash
sudo systemctl restart law.service qcluster.service
```

Run `manage.py` commands from the Kosmos checkout with its virtual
environment active. They read `config/.env` each time they run, so they
see a change without a restart.

## Choose a processor

Set `PAYMENT_PROCESSOR` to one of `fake`, `lawpay`, `stripe` or `confido`.
Any other value makes the payment pages fail.

| | `fake` | `lawpay` | `stripe` | `confido` |
|---|---|---|---|---|
| Service | None (simulation) | LawPay (AffiniPay) | Stripe | Confido Legal (Gravity Legal) |
| Card payments | Simulated | Yes | Yes, except cards that require 3-D Secure | Yes, credit and debit |
| eCheck (ACH) on the payment page | No | No | No | Yes |
| Operating and trust kept apart | No | Yes, by deposit account id | No: one Stripe account receives everything | Yes, by bank account id (both required) |
| Trust deposit confirmed automatically once it reaches the bank | No | No | No | Yes |
| How a webhook is trusted | Not applicable | Unsigned. Kosmos fetches the transaction from LawPay with the secret key | `Stripe-Signature` header checked against the signing secret | `X-Signature` header checked against the signing secret, then the transaction is fetched from Confido |
| Sandbox or live chosen by | Not applicable | Which keys you set | Which keys you set | The API and script URLs, plus the key |
| Script the payment page loads | None | `cdn.affinipay.com` | `js.stripe.com` | The URL in `CONFIDO_HOSTED_FIELDS_URL` |

Points the table cannot hold:

- **LawPay eCheck.** The adapter has variables for eCheck deposit accounts
  (`LAWPAY_OPERATING_ECHECK_ACCOUNT_ID`, `LAWPAY_TRUST_ECHECK_ACCOUNT_ID`)
  but the payment page does not offer eCheck for LawPay, and no setting
  turns it on. Those two variables have no effect today.
- **Stripe and trust money.** The Stripe adapter ignores whether a charge
  is a trust deposit. A trust deposit request paid through Stripe lands in
  the firm's single Stripe account, and Kosmos still records it in the
  trust ledger. Decide whether that meets your trust accounting rules
  before sending trust deposit requests with Stripe.
- **Stripe and 3-D Secure.** A card that needs extra authentication is
  declined with "This card requires additional authentication; please try
  another."
- **Trust confirmation.** A trust deposit made online is recorded as
  unconfirmed. Only the Confido adapter reports when the money has been
  deposited in the bank, which flips the deposit to confirmed. With LawPay
  and Stripe, staff confirm the deposit by hand in the trust ledger.
- **Refunds.** Kosmos has no refund action. Refund in the processor's own
  dashboard. When the processor reports the refund, Kosmos records the new
  status on the payment but leaves it applied to the invoice, so staff
  must correct the ledger by hand.

## Set up LawPay

1. Put the test keys in `config/.env`:

    ```
    LAWPAY_PUBLIC_KEY=<test public key>
    LAWPAY_SECRET_KEY=<test secret key>
    ```

    A test key reaches only test accounts and a live key only live
    accounts. There is no separate sandbox URL: leave `LAWPAY_API_BASE`
    at its default.

2. List the merchant's deposit accounts:

    ```bash
    python manage.py lawpay_accounts
    ```

    The command prints the merchant name, then one line per account,
    labelled `operating`, `TRUST` or `eCheck`, each with its `id=`.
    If it warns that no accounts are provisioned, the key's environment
    (test or live) has no deposit accounts yet. That has to be fixed with
    LawPay before a charge can succeed.

3. Copy the ids into `config/.env`:

    ```
    LAWPAY_OPERATING_CARD_ACCOUNT_ID=<id of the operating account>
    LAWPAY_TRUST_CARD_ACCOUNT_ID=<id of the TRUST account>
    ```

    Invoice and payment-request charges go to the operating id. Trust
    deposit requests go to the trust id.

    !!! warning

        If an id is blank, Kosmos sends the charge without an account and
        the LawPay gateway picks its primary account. Set
        `LAWPAY_TRUST_CARD_ACCOUNT_ID` before anyone sends a trust deposit
        request, or the deposit may not land in the trust account.

4. Set `PAYMENT_PROCESSOR=lawpay` and restart both services.

5. In LawPay, register a webhook that POSTs transaction events to:

    ```
    https://kosmos.example.com/webhooks/lawpay/
    ```

    Keep the trailing slash. There is no secret to copy: LawPay
    deliveries are not signed and Kosmos does not check where they came
    from. Kosmos reads only the transaction id from the first event in
    the delivery, then fetches that transaction from LawPay with
    `LAWPAY_SECRET_KEY` and acts on what LawPay returns.

6. To go live, replace both keys with the live keys, run
   `lawpay_accounts` again (live accounts have different ids), update the
   account ids, restart both services, and make sure the webhook is
   registered for the live environment.

## Set up Stripe

The firm uses its own Stripe account and its own keys.

1. Put the test-mode keys in `config/.env`:

    ```
    STRIPE_PUBLISHABLE_KEY=<publishable key>
    STRIPE_SECRET_KEY=<secret key>
    ```

2. In Stripe, create a webhook endpoint for:

    ```
    https://kosmos.example.com/webhooks/stripe/
    ```

    Keep the trailing slash. Subscribe it to exactly these event types:

    - `payment_intent.succeeded`
    - `payment_intent.processing`
    - `payment_intent.payment_failed`
    - `payment_intent.canceled`
    - `charge.refunded`

    Kosmos ignores every other event type and logs a warning for each
    one it receives.

3. Copy the endpoint's signing secret into `config/.env`:

    ```
    STRIPE_WEBHOOK_SECRET=<signing secret>
    ```

    Kosmos checks the `Stripe-Signature` header of each delivery against
    this secret. If the secret is blank or wrong, every delivery is
    ignored.

4. Set `PAYMENT_PROCESSOR=stripe` and restart both services.

5. To go live, replace the two keys with the live keys and
   `STRIPE_WEBHOOK_SECRET` with the signing secret of the live endpoint,
   then restart both services.

There are no account ids to configure and no account-listing command for
Stripe.

## Set up Confido Legal

Confido Legal was formerly Gravity Legal, which is why its URLs say
`gravity-legal.com`.

1. Put the sandbox API key in `config/.env`:

    ```
    CONFIDO_API_KEY=<sandbox API key>
    ```

    Leave `CONFIDO_API_BASE` and `CONFIDO_HOSTED_FIELDS_URL` unset for
    now. Their defaults point at the Confido sandbox.

2. Run the pre-flight check to see the firm's bank accounts:

    ```bash
    python manage.py confido_check
    ```

    It prints the endpoint with `[SANDBOX]` or `[LIVE]`, then each bank
    account with its nickname, `id=` and `category=`. On this first run
    it also reports that the two account ids are not set and ends with
    `PRE-FLIGHT FAILED`. That is expected.

3. Copy the ids into `config/.env`:

    ```
    CONFIDO_OPERATING_BANK_ACCOUNT_ID=<id of the operating account>
    CONFIDO_TRUST_BANK_ACCOUNT_ID=<id of the trust account>
    ```

    Both are required. Confido has no default account, so a payment page
    whose account id is missing fails with a server error.

4. Run `python manage.py confido_check` again until it ends with
   `PRE-FLIGHT PASSED`. The check confirms the key authenticates, that
   both ids belong to this firm, and that a payment session can be
   started for each account. It starts and abandons one session per
   account and charges nothing. The command exits with status 0 even
   when the check fails, so read the output.

5. In Confido, allow the Kosmos hostname (`kosmos.example.com`) to load
   the hosted payment fields. The code comments call this dashboard
   setting Trusted Domains. Until the hostname is allowed, each field on
   the payment page shows "error loading field".

6. In Confido, register a webhook that POSTs to:

    ```
    https://kosmos.example.com/webhooks/confido/
    ```

    Keep the trailing slash. Subscribe it to Confido's transaction
    events, so that Kosmos hears when a transaction is deposited,
    refunded, voided or returned. The adapter names four reversal events
    (`transaction.refunded`, `transaction.partially_refunded`,
    `transaction.ach_returned`, `transaction.voided`) but does not filter
    by type: for any event that names a transaction it fetches that
    transaction's current state from Confido and acts on that.

7. Copy the webhook's signing secret into `config/.env`:

    ```
    CONFIDO_WEBHOOK_SECRET=<signing secret>
    ```

    Kosmos accepts a delivery only if its `X-Signature` header equals the
    base64-encoded HMAC-SHA512 of the raw request body, keyed with this
    secret. If the secret is blank or wrong, every delivery is ignored.

8. Set `PAYMENT_PROCESSOR=confido` and restart both services.

9. To go live, set the live URLs and the live credentials together:

    ```
    CONFIDO_API_BASE=https://api.gravity-legal.com/v2
    CONFIDO_HOSTED_FIELDS_URL=https://js.gravity-legal.com/hosted-fields.js
    CONFIDO_API_KEY=<live API key>
    CONFIDO_OPERATING_BANK_ACCOUNT_ID=<live operating id>
    CONFIDO_TRUST_BANK_ACCOUNT_ID=<live trust id>
    CONFIDO_WEBHOOK_SECRET=<signing secret of the live webhook>
    ```

    Repeat steps 4 to 6 against the live environment, then restart both
    services. `confido_check` warns while the endpoint still contains
    `sandbox`, and reports an id that is "not found among this firm's
    accounts" when a sandbox id is left in place.

Two behaviours to know about:

- **Kosmos sends client details to Confido.** With each charge it sends
  the paying client's name, email and phone and the matter's name, so the
  transaction is filed under a client and matter in Confido. Kosmos
  creates those records if they do not exist, with external ids of the
  form `kosmos-client-<id>` and `kosmos-matter-<id>`, and appends
  ` #<matter id>` to the matter name. If this step fails the charge still
  goes ahead.
- **Credit and debit cards.** Confido rejects a card charge whose declared
  type (credit or debit) does not match the card. The payment page passes
  the type the hosted fields detected, and if Confido still reports a
  mismatch Kosmos retries once with the other type. Nothing needs
  configuring.

## Links and email settings

Three more variables shape the emails and their links.

### Link lifetime: `INVOICE_PAY_LINK_MAX_AGE`

How long a link stays valid, in seconds, counted from when the email was
sent. The default is 7776000 (90 days). It applies to invoice links,
payment request links, trust deposit request links and the PDF download
links on the payment pages. The age is checked when the link is opened,
so lowering the value also shortens links that were already sent. An
expired link shows "This payment link has expired. Please contact us for
a new one." Sending the invoice or request again issues a fresh link.

Links are signed with `SECRET_KEY`. Changing `SECRET_KEY` invalidates
every link already sent.

### Link host: `PUBLIC_BASE_URL`

Scheme and host for links built when there is no web request, for example
`https://kosmos.example.com`. Today every email that carries a pay link
is sent while a staff member is using Kosmos, and the link takes its
scheme and host from that staff member's request. `PUBLIC_BASE_URL` is
only the fallback. Set it anyway, and make sure staff reach Kosmos at the
same public hostname clients will use.

### Sender: `BILLING_FROM_EMAIL`

The From address of invoice and payment-request emails. Only the address
part is used: the display name is always the firm's name from Kosmos's
firm settings followed by "Billing". When the firm settings hold a
billing email (or, failing that, a general firm email), replies are
directed there and not to this address. If `BILLING_FROM_EMAIL` is unset
it falls back to `DEFAULT_FROM_EMAIL`.

## How payments settle

1. **The charge.** When the client submits the payment page, Kosmos
   charges the token and records the payment straight away. A card
   payment is final at this point. An eCheck is recorded as `pending`:
   the invoice shows as paid, provisionally, until the bank transfer
   clears or fails some days later.

2. **The webhook.** The processor later POSTs to
   `/webhooks/<processor>/`. Kosmos answers `200` at once and queues the
   delivery for the background worker. The worker verifies it (see the
   table above) and applies the result. A `200` in the processor's
   delivery log therefore means Kosmos received the delivery, not that
   it accepted it.

3. **The result.**

    - *Settled.* The payment's status is updated. Under Confido, a trust
      deposit is also marked confirmed once Confido reports the money
      deposited.
    - *Failed, returned or voided.* An operating payment is removed and
      its invoices go back to unpaid. An unconfirmed trust deposit is
      removed. A trust deposit that staff had already confirmed is left
      in place and flagged, for staff to reconcile by hand. In each case
      Kosmos emails the addresses in `ADMINS`.
    - *Refunded.* Only the status is recorded. See the note on refunds
      above.

Because the worker does the verifying, **webhooks that arrive while the
worker is stopped wait in the queue** and are applied when it starts.

### The backstop: `reconcile_pending`

A webhook that never arrives would leave an eCheck `pending`, or a trust
deposit unconfirmed, for good. The `reconcile_pending` command covers
that. It asks the processor for the current state of every in-flight
online payment and applies it through the same rules as a webhook:

```bash
python manage.py reconcile_pending --dry-run   # report only
python manage.py reconcile_pending             # apply
```

It checks operating payments that are still `pending`, and online trust
deposits that are `pending` or not yet confirmed. It prints one line per
row, or `Nothing to reconcile.` It is safe to run repeatedly.

**Nothing runs this command for you.** It is not one of the
[scheduled jobs](../../reference/schedules.md) that `setup_schedules`
installs. Run it from cron, as the user that owns the checkout. For
example, hourly (replace `/srv/kosmos` with your checkout):

```
15 * * * * cd /srv/kosmos && .venv/bin/python manage.py reconcile_pending >> logs/reconcile_pending.log 2>&1
```

Alternatively, add a Django-Q schedule (for example in the Django admin)
that calls `apps.invoicing.pay.reconcile.poll_pending`. The worker then
runs it, and `setup_schedules` neither creates nor removes it.

Things to expect in its output:

- Each row is fetched with the processor that took the payment, not the
  one currently selected. If you change processors, keep the old one's
  credentials in `config/.env` until its in-flight payments have settled.
- With LawPay and Stripe, an online trust deposit is listed on every run
  until staff confirm it by hand.
- Rows created with the `fake` processor always report `fetch failed:
  Unknown transaction`. The simulation keeps its transactions in the
  memory of the process that took the charge.

The command is listed with the others in the
[command reference](../../reference/commands.md#invoicing).

## Check it works

### With the simulation

On a test instance with `PAYMENT_PROCESSOR=fake`:

1. Send an invoice to an address you control and open the link in the
   email.
2. The page shows a "Dev simulation" notice and plain card inputs. Fill
   in every field, using any card number that does not end in `0002`,
   and submit. The page answers "Payment received. Thank you."
3. In Kosmos the invoice is paid, by a payment whose detail reads
   `Online payment · fake`.
4. Repeat with a card number ending in `0002`. The page answers "Card
   declined (fake)." and nothing is recorded.

### With a processor's sandbox

1. Finish the setup section for your processor using sandbox or test
   credentials.
2. Send an invoice for a small amount to an address you control and open
   the link. The "Dev simulation" notice must be gone, and the
   processor's own card fields must load.
3. Pay with one of the processor's published test cards. The page
   answers "Payment received. Thank you."
4. Check both sides: the invoice is paid in Kosmos (the payment's detail
   reads `Online payment · ` followed by the processor name), and the
   transaction appears in the processor's sandbox dashboard.
5. Check the webhook. The processor's delivery log should show a
   delivery to `/webhooks/<processor>/` answered with `200`. Then make
   sure Kosmos accepted it:

    ```bash
    grep "webhook" logs/django.log
    ```

    No line containing `webhook ignored` should have appeared for your
    test.

6. Run `python manage.py reconcile_pending --dry-run`. A card payment on
   an invoice is final, so it is not listed: if nothing else is in
   flight the command prints `Nothing to reconcile.` After an eCheck or
   a trust deposit it lists the row and the state the processor reports.
7. If the firm will use trust deposit requests, send one, pay it, and
   confirm in the processor's dashboard that the money went to the trust
   account. In Kosmos the deposit appears in the client's trust ledger,
   unconfirmed.

Only then switch to live credentials, and repeat steps 2 to 5 once with
a real card and a small amount.

## Troubleshooting

Warnings from both the web service and the worker go to `logs/django.log`
in the checkout, and to each service's journal
(`journalctl -u law`, `journalctl -u qcluster`).

**The payment page still shows "Dev simulation".**
`PAYMENT_PROCESSOR` is still `fake`, or the web service was not restarted
after the change.

**The payment page returns a server error.**
The processor could not be set up. The log names the cause:
`LAWPAY_SECRET_KEY is not configured.`,
`STRIPE_SECRET_KEY is not configured.`,
`CONFIDO_API_KEY is not configured.`,
`CONFIDO_OPERATING_BANK_ACCOUNT_ID is not configured.` (or the trust
one), or `Unknown PAYMENT_PROCESSOR`. Under Confido the page also fails
when Confido refuses to start a payment session, because the session is
created as the page loads. Run `python manage.py confido_check`.

**"Payment form failed to load. Please refresh."**
The browser could not load the processor's script (see the last row of
the table above). Check for a content security policy, proxy rule or
network filter that blocks that host.

**Confido fields show "error loading field".**
The Kosmos hostname is not an allowed domain in Confido (setup step 5).
The browser console shows the detail on lines beginning
`Confido field error:`.

**`confido_check` fails with "No Emergepay Auth Token".**
The key authenticates but the firm is not yet enabled to take payments
in that Confido environment. That is for Confido to resolve.

**A debit card is rejected with "card type is not credit, but CREDIT
method was requested".**
Kosmos handles this mismatch itself by retrying with the other card
type. If the payer still sees the message, both attempts were refused by
Confido.

**Stripe: "This card requires additional authentication".**
The card needs 3-D Secure, which Kosmos does not support. The payer must
use another card.

**The processor shows deliveries answered `200`, but nothing changes in
Kosmos.**
Look at the worker first, then the log:

- If the worker is not running, deliveries are queued and not yet
  processed. Start it.
- `Unverifiable confido webhook ignored: Bad Confido webhook signature.`
  or `Unverifiable stripe webhook ignored: Bad Stripe webhook: ...`
  means the signing secret in `config/.env` does not match the endpoint
  at the processor, is blank, or was changed without restarting the
  worker.
- `Unverifiable stripe webhook ignored: Unhandled Stripe event ...` is
  harmless. Remove that event type from the endpoint to stop it.
- `Unverifiable lawpay webhook ignored: Could not confirm transaction
  ...` means LawPay would not return the transaction to this secret key,
  for example a live webhook reaching an instance that holds test keys.
- `Webhook for unknown processor '...' ignored` means the name in the
  URL is not `lawpay`, `stripe` or `confido`, or that processor's secret
  or API key is not set.

Kosmos has already answered `200`, so the processor will not send an
ignored delivery again. After fixing the cause, run
`python manage.py reconcile_pending` to catch up.

**A secret was rotated and webhooks stopped working.**
Restart the worker as well as the web service. The worker verifies
webhooks, and it keeps the old secret in memory until it restarts.

**eChecks stay pending, or trust deposits stay unconfirmed, for longer
than the bank should take.**
No webhook is arriving. Look for `POST /webhooks/` lines in the web
server's access log (`logs/access.log` with the bundled gunicorn
configuration). If there are none, check at the processor that the
endpoint exists, is enabled, belongs to the same environment (sandbox or
live) as your keys, and points at your public hostname with the trailing
slash. Then run `python manage.py reconcile_pending`, and schedule it if
you have not. Remember that with LawPay and Stripe a trust deposit is
never confirmed automatically.

**The processor reports `429` responses from the webhook URL.**
Kosmos accepts at most 240 webhook deliveries a minute from one address.
Each web worker process keeps its own count.

**The payer sees "Too many attempts. Please wait a moment."**
Kosmos allows 20 payment attempts in five minutes from one address, also
counted per web worker process.

**A link says it has expired or is invalid.**
Expired means it is older than `INVOICE_PAY_LINK_MAX_AGE`. Send the
invoice or request again. Invalid means the link was cut short in
transit, or `SECRET_KEY` has changed since it was sent.

**Links in the emails point at the wrong host.**
The link is built from the address the sending staff member used to
reach Kosmos. Have staff use the public hostname, and make sure the
reverse proxy passes the original host and scheme through to Kosmos.

**`reconcile_pending` prints `fetch failed`.**
The row was made with the `fake` processor, or with a processor whose
credentials are no longer in `config/.env`.

**Nobody was told about a returned eCheck.**
The notice goes to `ADMINS` and a send failure is not reported. Check
that `ADMINS` is set and that outbound email works.

The contract every adapter implements is in
[`apps/invoicing/processors/base.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/invoicing/processors/base.py),
with one module per processor beside it, and the settlement rules are in
[`apps/invoicing/pay/reconcile.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/invoicing/pay/reconcile.py).
