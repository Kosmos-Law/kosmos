# Security checklist

What to check before a Kosmos server holds real client data, and what the
code does and does not do for you. Each item says where the behaviour comes
from, so you can confirm it against the version you run.

## The short list

1. `DEBUG=False`, a private `SECRET_KEY`, `ALLOWED_HOSTS` and
   `CSRF_TRUSTED_ORIGINS` set to your host, `EMAIL_BACKEND=smtp`.
   See [Core settings](#core-settings).
2. TLS issued with certbot before anyone signs in, and the port 80
   redirect in place. See [TLS and nginx](#tls-and-nginx).
3. `KOSMOS_SEAM_KEY` and `MAILGUN_WEBHOOK_SIGNING_KEY` set only for the
   features you use. While blank, their endpoints refuse every request.
   See [Endpoints that stay closed until you set a secret](#endpoints-that-stay-closed-until-you-set-a-secret).
4. `PAYMENT_PROCESSOR` set to `none`, or to a real processor with its
   webhook secret. Never `fake` on a server that emails invoices.
   See [Payment webhooks](#payment-webhooks).
5. Superuser accounts kept few. See [Sign-in](#sign-in).
6. `config/.env` and the Google token directory readable only by the
   service account. See [File permissions](#file-permissions).
7. `media/` never served by the web server.
   See [Uploaded files](#uploaded-files).
8. Every new user's permissions reviewed, with the limits of those
   permissions understood.
   See [Access inside the firm](#access-inside-the-firm).

## Core settings

All of these live in `config/.env`. Their defaults are in the
[environment reference](../reference/environment.md#core).

| Setting | What to set | Why |
|---|---|---|
| `DEBUG` | `False` | With it on, error pages show source code and settings, Django serves `media/` to anyone when storage is local, OAuth is allowed over plain HTTP, email defaults to the console, and the cookie and proxy settings under [Django security settings](#django-security-settings) are not applied. |
| `SECRET_KEY` | A long random value used nowhere else | It signs sessions, password-reset links, payment links and intake-form links. Anyone who has it can forge them. The value in `config/.env.dev` is public. |
| `ALLOWED_HOSTS` | Your host name only | Requests for any other host are refused. |
| `CSRF_TRUSTED_ORIGINS` | `https://kosmos.example.com` | The origin Django accepts form posts from, in addition to the host the request itself names. |
| `ENV` | `prod` | |
| `EMAIL_BACKEND` | `smtp` | While it is `console`, sign-in codes and password-reset links are written to the log instead of being sent. |

When `scripts/install.sh --prod` generates `config/.env`, it writes the
first five, generates the key and sets `PAYMENT_PROCESSOR=none`. It leaves
`EMAIL_BACKEND=console` and every integration secret blank. It never edits
a `config/.env` that already exists, so on a server that began as a
development install, check each of these by hand.

Changing `SECRET_KEY` later signs every user out and invalidates every
payment link, intake-form link and password-reset link already sent.

## TLS and nginx

The site file the installer renders,
[`deploy/nginx/kosmos.conf`](https://github.com/Kosmos-Law/kosmos/blob/dev/deploy/nginx/kosmos.conf),
listens on port 80 only. Until you run certbot, nobody can sign in: a
production instance marks its cookies `Secure`, and a browser does not keep
or return such cookies over plain HTTP (see
[Django security settings](#django-security-settings)). Anything typed into
the sign-in form in the meantime still crosses the network unencrypted.
Run certbot before you hand out an account.

```bash
sudo certbot --nginx -d kosmos.example.com
```

Certbot rewrites the site file with the TLS listeners and the redirect from
port 80. The installer does not overwrite a certbot-managed file unless you
pass `--force`.

What the templates add:

| File | What it does |
|---|---|
| `kosmos-security.conf` | Sends `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: strict-origin-when-cross-origin` on responses, including error responses. Refuses any path with a component that starts with a dot (`.env`, `.git`). |
| `kosmos-ratelimit.conf` | Defines two request-rate zones keyed on the client address: `general` at 10 requests a second and `login` at 5 requests a minute. Installed only when no other nginx file already defines a `login` zone. |
| `limit-login.conf` | Applies the `login` zone with a burst of 5 to paths that begin `/accounts/login` or `/admin/login`. That covers the password step, the code step, and `/admin/login/`, which only redirects to the password step. |
| `kosmos.conf` | Applies the `general` zone with a burst of 20 to everything else that reaches the application. Limits request bodies to 100 MB. Serves `/static/` straight from the checkout. Has no location for `media/`. Passes the request on with the distribution's `proxy_params`, which set `Host`, `X-Forwarded-For` and `X-Forwarded-Proto`. |

What they do not add:

- No `Strict-Transport-Security` header and no `Content-Security-Policy`.
- The three security headers are not sent on `/static/` responses. Those
  two locations set their own `Cache-Control` header, and nginx does not
  inherit server-level `add_header` lines into a location that has its own.
- A request over the limit is answered with nginx's default status for
  `limit_req`, which is 503.
- `/accounts/password_reset/` is under the `general` zone only.
- `/static/` and `/favicon.ico` are not rate limited.

To add HSTS, put this in the TLS `server` block of the certbot-managed site
file once you are sure the site will stay on HTTPS:

```nginx
add_header Strict-Transport-Security "max-age=31536000" always;
```

## Django security settings

[`config/settings.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/config/settings.py)
reads only the variables in the environment reference. None of the settings
below can be changed from `config/.env`, except that three of them follow
`DEBUG`.

| Setting | In effect | Consequence |
|---|---|---|
| `SECURE_PROXY_SSL_HEADER` | Set when `DEBUG` is off: `("HTTP_X_FORWARDED_PROTO", "https")` | Django takes the scheme of a request from the `X-Forwarded-Proto` header that nginx sets. Addresses it builds from a request, such as the configuration block on **Settings → Claude Desktop**, begin with `https://`. |
| `SESSION_COOKIE_SECURE` | Set when `DEBUG` is off: on | The session cookie is marked `Secure`. A browser sends it over HTTPS only. |
| `CSRF_COOKIE_SECURE` | Set when `DEBUG` is off: on | Same for the CSRF cookie. |
| `SECURE_SSL_REDIRECT` | Not set (off) | Django never redirects to HTTPS. Certbot's nginx redirect is the only one. |
| `SECURE_HSTS_SECONDS` | Not set (0) | No HSTS header from Django. |
| `SESSION_COOKIE_HTTPONLY` | Django default (on) | Scripts cannot read the session cookie. |
| `SESSION_COOKIE_SAMESITE`, `CSRF_COOKIE_SAMESITE` | Django default (`Lax`) | |
| `SESSION_COOKIE_AGE` | Set: 56 days | See [session length](users.md#how-long-a-session-lasts). |
| `SESSION_SAVE_EVERY_REQUEST` | Set: on | Each request renews the 56 days. |
| `X_FRAME_OPTIONS` | Set: `SAMEORIGIN` | |
| `SECURE_CONTENT_TYPE_NOSNIFF` | Django default (on) | |
| `SECURE_REFERRER_POLICY` | Django default (`same-origin`) | Application responses carry this value and the one nginx adds. |
| `AUTH_PASSWORD_VALIDATORS` | Set: Django's four standard checks | Applied by password reset, `createsuperuser` and the Django admin only. See [Add a user](users.md#add-a-user). |
| Content Security Policy | None | |

What this leaves to you:

- TLS has to be in place before the first sign-in. With `DEBUG` off, both
  cookies are `Secure`, so a production instance cannot be signed into
  over plain HTTP.
- Django believes the `X-Forwarded-Proto` header. The `proxy_params` file
  that the nginx template includes sets it from the real scheme of each
  request, replacing anything the client sent. If you write your own proxy
  configuration, set the header the same way.
- Nothing sends an HSTS header, and only nginx redirects port 80. Keep
  that redirect, and add the HSTS header above.

## Sign-in

How sign-in works is described in
[Users and permissions](users.md#how-sign-in-works). The points that
matter for hardening
([`apps/accounts/views.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/accounts/views.py)):

- The application keeps no count of failed passwords and never locks an
  account. The nginx `login` zone is the only brake on password guessing.
  Do not remove it, and do not put the application behind a proxy that
  hides client addresses from nginx.
- The emailed code is six digits, generated with Python's `secrets`
  module, and stored unhashed in the database until it is used, replaced,
  found expired or discarded.
- The code expires five minutes after it was created.
- After five wrong codes (`MAX_CODE_ATTEMPTS`) the code is deleted and the
  user has to pass the password step again, which issues a new code. The
  count is kept on the code itself, so it is the same five guesses however
  many browser sessions try it.
- `/admin/login/` has no form of its own. It redirects to
  `/accounts/login/`, so the Django admin is reached only through the
  password and the emailed code.
- The address a sign-in link asks to return to (`next`) is followed only
  when it stays on the same host. Any other value is dropped and the user
  lands on the task list.

The Django admin is reachable from the internet, behind the same sign-in
as the rest of the application. Restricting it to known addresses is
optional extra hardening. To do so, add a location to the site file (the
address is an example):

```nginx
location ^~ /admin/ {
    allow 203.0.113.10;
    deny all;
    limit_req zone=general burst=20 nodelay;
    include proxy_params;
    proxy_pass http://unix:/run/law.sock;
}
```

## Uploaded files

Documents, invoice PDFs and email attachments are confidential and are
never given a public address.

- With `STORAGE_BACKEND=local`, files are kept in `media/`. Django routes
  that directory only when `DEBUG` is on
  ([`config/urls.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/config/urls.py)),
  and the nginx template has no location for it. Files reach a browser only
  through views that require a signed-in session or, for an invoice PDF,
  the signed link emailed to the client.
  [`config/tests/test_media_security.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/config/tests/test_media_security.py)
  holds this in place.
- The one exception is `media/company/`, which holds the firm logo. It is
  served to anyone at `/media/company/…` because the public payment and
  intake pages show it. Upload nothing else there.
- With `STORAGE_BACKEND=s3`, nothing under `media/` is routed. Files are
  read through the storage API, and links to them are signed and expire.
  Kosmos sets no access rule on uploads, so keep the bucket private.

Never add an nginx `location` or alias for `media/`.

Document downloads and the document viewer are under `/case/`, so they
check matter membership as well as the session.
See [Access inside the firm](#access-inside-the-firm).

## Endpoints that stay closed until you set a secret

Two shared secrets are blank after a fresh install. The endpoints they
guard are routed whether or not you use the feature, but while a secret is
blank its endpoints refuse every request with HTTP 403. If you do not use
a feature, leave its secret blank.

### `KOSMOS_SEAM_KEY`

Guards three endpoints meant for a firm's own website or intake
application
([`apps/intakes/api_views.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/intakes/api_views.py)).
A caller must send the key in an `X-Seam-Key` header, which is compared
with the setting in constant time. A caller that holds the key can:

| Endpoint | What a caller with the key can do |
|---|---|
| `GET /api/intakes/search/` | Read prospective clients' names, phone numbers, email addresses, status and practice area. A blank query returns the 20 most recent open intakes. |
| `POST /api/receive-inquiry/` | Create an intake, or add a note to an existing intake that matches an email address or phone number. |
| `POST /api/receive-intake/` | Create an intake, add a note to any intake by its number, or replace the text of an existing note on that intake. |

These endpoints have no application rate limit, and the key is the only
thing that protects them. Generate a long random one:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Put the output in `config/.env` as `KOSMOS_SEAM_KEY=…`, restart the web
service, and give the calling application the same value. Every request
without that exact header is refused with HTTP 403.

### `MAILGUN_WEBHOOK_SIGNING_KEY`

Guards `POST /api/inbound-email/`
([`apps/intakes/inbound.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/intakes/inbound.py)).
A post must carry Mailgun's HMAC-SHA256 signature made with this key and a
timestamp no more than five minutes old. A post that passes is then
accepted only when the recipient matches `INTAKE_INBOUND_RECIPIENT` and
the From address belongs to an active user. While the variable is blank no
signature can be verified, and every post is refused with HTTP 403.

To use the feature, set the key as described in
[Intakes from forwarded email](integrations/inbound-email.md).

## Payment webhooks

`POST /webhooks/<processor>/` needs no sign-in. The processor is chosen by
the name in the path, not by `PAYMENT_PROCESSOR`. The view always answers
200 and hands the body to the background worker, which verifies it
([`apps/invoicing/pay/reconcile.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/invoicing/pay/reconcile.py)).
An event that fails verification is logged and ignored. A verified event
can only change a payment or trust deposit that Kosmos itself recorded
for that processor with that transaction id.

| Path | How a delivery is verified | If the secret is blank |
|---|---|---|
| `/webhooks/lawpay/` | LawPay does not sign. The body is used only to learn a transaction id; Kosmos then fetches that transaction from the LawPay API with `LAWPAY_SECRET_KEY` and acts on the fetched status. | The processor does not load without `LAWPAY_SECRET_KEY`, and the event is ignored. |
| `/webhooks/stripe/` | The `Stripe-Signature` header is checked against `STRIPE_WEBHOOK_SECRET`. A verified payload is trusted as sent. | Every delivery is rejected. The processor loads with `STRIPE_SECRET_KEY` alone, so check that the webhook secret is set too. |
| `/webhooks/confido/` | The `X-Signature` header must be the HMAC-SHA512 of the raw body under `CONFIDO_WEBHOOK_SECRET`. Kosmos then fetches the transaction from Confido and acts on the fetched status. | Every delivery is rejected. |
| `/webhooks/fake/` | Not verified. The simulated processor trusts the body, but acts only on simulated transactions held in the memory of the process that handles it. | Not applicable. |
| `/webhooks/none/` | Every delivery is rejected. | Not applicable. |

When deliveries are rejected or never arrive, payments stay as they were
recorded until something asks the processor. The worker's hourly
[`payments-reconcile` job](../reference/schedules.md) does that for every
payment and trust deposit still in flight, and `manage.py
reconcile_pending` does the same on demand. It is listed in the
[command reference](../reference/commands.md).

`PAYMENT_PROCESSOR` decides what the public payment page does. Invoice
emails carry a link to that page.

- `none` switches online payment off. The page shows the amount due and
  the invoice or statement to download, and asks the client to contact the
  firm. Nothing can be charged or recorded. The installer writes this
  value for a production install.
- `fake` is for development. The page shows a simulated form, and
  submitting it records the invoice as paid although no money moves. It is
  the built-in default when the variable is missing, and the value in
  `config/.env.dev`. On a server that emails invoices, the recipient could
  mark an invoice paid.
- `lawpay`, `stripe` and `confido` are the real processors. Setting them
  up is in [Online payments](integrations/payments.md).

A trust deposit is refused, not sent to the wrong account, when the
processor cannot guarantee where it lands: always under Stripe, which pays
into a single account, and under LawPay or Confido while the trust account
id is blank. When a processor cannot serve a payment page as configured (a
missing key or account id, an unknown processor name), the client sees
"Online payment is not available right now. Please contact us." with HTTP
503, and the reason is written to the log.

## Application rate limiting

The public payment, intake-form, inbound-email and webhook routes have
their own limits in addition to nginx
([`utils/ratelimit.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/utils/ratelimit.py)).
The figures are in the
[table of routes that need no sign-in](../reference/permissions.md#routes-that-need-no-sign-in).
Know their limits:

- The counters live in Django's default cache, which `config/settings.py`
  sets to in-process memory. Each gunicorn worker counts separately, so
  with the template's three workers a client gets up to three times the
  stated figure. The counters are lost when the service restarts.
- The client address is the last entry of the `X-Forwarded-For` header,
  which is the one nginx appends, so a client cannot choose it. If another
  proxy sits in front of nginx, that entry is the proxy's address and
  every client behind it shares one counter.
- Sign-in, password reset, the three `KOSMOS_SEAM_KEY` endpoints, the
  health checks and the token-authenticated APIs have no application limit
  at all.

Treat these limits as a brake on scripted abuse, not as access control.
The signed token in each public link is the access control.

## Access inside the firm

The role and permission switches are described in
[Users and permissions](users.md), and every check is listed in the
[permissions matrix](../reference/permissions.md). Before you rely on them:

- A new user has every permission until you switch some off.
- Restricting a user to assigned matters closes those matters' pages, case
  workspace and document downloads to everyone else. It does not filter
  the task list, the calendar, contacts or practice-wide search, so it is
  not an ethical screen.
- The permission switches are enforced by address, with a few leaks that
  the matrix lists: rates and fees in the time list, and intake names in
  search.
- Nothing stops an admin from demoting or deactivating the last admin.
  Recovery is `createsuperuser` from the shell.
- A user's API token (Claude Desktop, LibreOffice companion) never expires
  and is stored unhashed. It stops working when the user is deactivated
  and works again if they are reactivated. Only the user can rotate or
  revoke it.
- Deactivating a user does not disconnect a Gmail mailbox they connected.
  It keeps synchronizing until the user disconnects it.

## File permissions

| Path | Holds | What the installer does | What to do |
|---|---|---|---|
| `config/.env` | `SECRET_KEY`, the database password, every API key | Writes it with mode 600 | If you created it by hand: `chmod 600 config/.env` |
| `google/` (or `GOOGLE_DATA_DIR`) | The Google OAuth client secret and the Calendar, Contacts and Drive tokens | Creates the directory with default permissions. The application writes the token files with default permissions too | `chmod 700 google` and `chmod 600 google/*.json` |
| `media/` | Client documents, when storage is local | Creates the directory with default permissions | `chmod 700 media` |
| `logs/` | Application, gunicorn access and error logs. Access logs record full request paths, which include payment-link and form-link tokens | Creates the directory with default permissions. Installs `/etc/logrotate.d/kosmos`, which rotates the files weekly and keeps twelve copies (see [Log rotation](monitoring.md#log-rotation)) | `chmod 700 logs` |
| The database | Everything else, including each user's Gmail token, each user's API token and unexpired sign-in codes, all stored unencrypted | Creates a role with a random password in production | Restrict who can read the database and its backups |

The web service and the worker both run as the account that owns the
checkout, so owner-only permissions are enough for these four paths. nginx
runs as `www-data` and needs only `static/` and the directories above it.

## Change history

Kosmos records changes with django-simple-history. Each time a tracked
record is created, changed or deleted, a full copy of the row is stored
with the time, the kind of change and, for a change made in the browser,
the signed-in user. Changes made by the background worker or a management
command carry no user.

Tracked: users, contacts, matters and their proceedings, rates and
settlements, tasks, calendar events, checklists, time, expense and flat-fee
entries, invoices, payments, credits and their applications, payment
requests, trust transactions, intakes and intake forms, documents and the
other case records, notes, and AI conversations. Firm settings and synced
email are not tracked.

Limits:

- It records writes only. Nothing records who viewed or downloaded a
  record. Sign-ins are not logged beyond the "last login" time on the user.
- History is shown in the Django admin for the models registered there.
  There is no history screen in the application itself.
- History rows for users include the password hash as it was at the time.
  Protect database backups accordingly.

History grows without limit until you prune it. `clean_history` deletes
history rows older than a number of days (90 unless you pass `--days`) from
every history table. It is not scheduled. Decide how long your firm must
keep an audit trail, then run it by hand or from cron:

```bash
.venv/bin/python manage.py clean_history --days 365 --dry-run
.venv/bin/python manage.py clean_history --days 365
```

The first form reports what would be deleted and changes nothing.

## What leaves the server

Each of these is off until its keys are set.

- **AI providers** (Anthropic, Google Gemini): the matter material a chat
  or summary draws on (document text, notes, emails, timeline), text sent
  for semantic indexing, forwarded intake email, the firm's user names and
  titles, and the name and email address of the user who asked. Keys are in
  the [environment reference](../reference/environment.md#ai-and-research).
- **Google Workspace**: calendar events and contacts are synchronized in
  both directions. Drive files and Gmail messages are read into Kosmos.
  See [Google Workspace](integrations/google.md).
- **Payment processor** (LawPay, Stripe or Confido): the amount, a
  reference such as the invoice number, and, depending on the processor,
  the client's name, email address and phone number and the matter name.
  Card and bank details go from the client's browser to the processor and
  never reach Kosmos. Keys are in the
  [environment reference](../reference/environment.md#billing-and-payments).
- **CourtListener**: research queries, the citations being checked, and
  the text of each AI chat reply, which is posted to its citation lookup.
  See [AI providers and research](integrations/ai.md#what-is-sent-to-the-providers).
- **Mailgun**: receives mail forwarded to the intake address before Kosmos
  does. See [Intakes from forwarded email](integrations/inbound-email.md).
- **Your SMTP provider**: sign-in codes, password resets, invoices and
  payment requests, daily digests, and error reports to `ADMINS`, which
  include details of the failed request.
- **Object storage**, when `STORAGE_BACKEND=s3`: every uploaded file.
- **Claude Desktop**, for users who set it up: whatever that user's Claude
  reads from Kosmos goes to their machine and to Anthropic under their own
  account. See [Claude Desktop](integrations/claude-desktop.md).
- **Users' browsers** load scripts and styles from `unpkg.com`,
  `cdn.jsdelivr.net` and Google Fonts on every page, and the processor's
  script on the payment page. The pages do not pin these files with
  integrity hashes.

## Reporting a vulnerability

Follow
[`SECURITY.md`](https://github.com/Kosmos-Law/kosmos/blob/dev/SECURITY.md):
report it privately by email to `info@kosmos.law`, and do not publish
details until the fix is released.
