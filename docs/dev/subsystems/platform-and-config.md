# Platform and config

The platform is everything a request passes through before and after an
app's view: settings and the environment file, the URL root, the
middleware stack, storage, outgoing mail, logging and the health checks.
It lives in `config/` and `utils/`, with the two project middlewares in
`apps/accounts` and `apps/dash`. The operator's side of the same ground
is [Configuration](../../admin/configuration.md); this page is about how
the code reads it.

## Where the code is

| Module | What it holds |
|---|---|
| `config/settings.py` | The one settings module. Reads `config/.env`; no per-environment settings files. |
| `config/.env.example` | Every variable the application reads, with a comment that becomes its description in the generated reference. |
| `config/urls.py` | The URL root and the two media-routing functions. |
| `config/health.py` | The three health views. |
| `config/context.py` | The `env` and `integrations` context processors. |
| `config/helpers.py` | `normalize_phone()`, `dictfetchall()`, `MultipleOrderingFilter`, `timestamp_to_eastern()`, the `dump*` helpers. |
| `config/wsgi.py`, `config/asgi.py` | Entry points; gunicorn runs `config.wsgi:application`. |
| `apps/accounts/middleware.py` | `HtmxLoginRedirectMiddleware`, `PermissionMiddleware`. |
| `apps/dash/middleware.py` | `DailyDashCheckMiddleware`. |
| `utils/middleware.py` | `CurrentUserMiddleware` and `get_current_user()`. |
| `utils/models.py` | `AuditMixin`: `created_at`, `updated_at`, `created_by`, `updated_by`. |
| `utils/safe_markdown.py`, `utils/safe_json.py`, `utils/toasts.py`, `utils/links.py`, `utils/signing.py`, `utils/ratelimit.py`, `utils/mail.py` | The guards and helpers described below. |
| `templates/base.html`, `templates/base-minimal.html`, `templates/registration/base.html` | The base templates. |
| `config/tests/` | Tests for the platform pieces. |

## Settings and the environment

`config/settings.py` builds one `environ.Env` and calls
`environ.Env.read_env()` on `config/.env`, so the file is read at import
and every process (gunicorn, the worker, a management command) reads it
for itself. Because the systemd units carry no `EnvironmentFile`, a value
in `config/.env` is the only source; a change there is seen by a process
only when it restarts.

Two variables with no default decide the shape of a run:

- `DEBUG` (boolean). On: Django serves local media and static files
  itself, the console email backend is the default, templates are loaded
  uncached, and `OAUTHLIB_INSECURE_TRANSPORT` is set so Google OAuth works
  over plain HTTP. Off: `STATIC_ROOT` is set for `collectstatic`, the
  cached template loader is used (templates change only on a process
  restart), `SECURE_PROXY_SSL_HEADER` trusts nginx's
  `X-Forwarded-Proto`, and the session and CSRF cookies are marked
  secure.
- `ENV` (`prod` or `dev`). This is a deliberate second switch, because
  `DEBUG` is sometimes toggled for testing while `ENV` is stable. `dev`
  keeps sessions in files under `.dev-sessions/` instead of the database
  (the comment explains: a development database that is rebuilt from a
  snapshot would otherwise sign every device out). The `env`
  context processor passes the value to templates, which show the
  development banner, the dev favicon and `dev.css` when it is `dev`.

`PUBLIC_BASE_URL` is the scheme and host used by `utils/links.py` to
absolutize a path when there is no request to borrow a host from: a
payment link in an email sent by the worker. `absolute(path, request)`
prefers the request when one is given. `ALLOWED_HOSTS` and
`CSRF_TRUSTED_ORIGINS` are the usual Django lists.

There is no `DOMAIN` setting. `@DOMAIN@` is a placeholder in the
`deploy/` templates (the nginx `server_name`) that `scripts/install.sh`
fills in; the application never reads it.

The variables themselves are listed in the
[environment reference](../../reference/environment.md), generated from
`settings.py` and `.env.example`. `config/tests/test_docs_reference.py`
fails when a variable is read but not listed in `.env.example`, or listed
but unread, so a new `env("...")` call needs a line in `.env.example` and
a run of `scripts/gen_docs_reference.py`.

## URLs

`config/urls.py` mounts, in order: the three health URLs; `/` (the tasks
index); `/admin/login/`, replaced by `apps.accounts.views.admin_login`
before `admin.site.urls` because Django's own form takes a password
alone and would skip the emailed code; `accounts/` (the project's views,
then `django.contrib.auth.urls`); and then every app's `urls.py` included
at the root, each app choosing its own prefix. The public, tokenized
pages (the payment page and the client intake form) are ordinary
includes among them; they are public because their views are not
`@login_required`, not because of where they are mounted.

Static files are served by Django only through
`staticfiles_urlpatterns()`, which is active under `DEBUG`. Media is
handled by two functions at the bottom of the file:
`development_media_urlpatterns()` routes `media/` only when `DEBUG` is on
and the backend is local, and `public_branding_media_urlpatterns()`
routes `media/company/` (the firm logo, `Firm.logo`'s `upload_to`) under
local storage in every mode, because the public intake form and the
invoice PDF renderer load it by URL. Everything else in storage is
reached through a view that checks access and streams the file.

## Middleware

`MIDDLEWARE` runs Django's own stack first (security, session, common,
broken-link emails, CSRF, auth, messages, clickjacking), then five
project entries. On the way in they run in this order:

1. **`DailyDashCheckMiddleware`** (`apps/dash/middleware.py`). Once a
   day, the first full-page request from a signed-in user is redirected
   to the Dash. When the request is for the Dash itself, the middleware
   writes today's date to `CustomUser.last_dash_check` (its docstring
   says the view does this; the code does it here), so the check follows
   the user across devices. It skips `/accounts/`,
   `/static/`, `/media/`, and every HTMX or XHR request, so a partial swap
   is never answered with a redirect.
2. **`CurrentUserMiddleware`** (`utils/middleware.py`). Stores the request
   user in a thread local for the length of the request and clears it in
   a `finally`. `AuditMixin.save()` reads it through `get_current_user()`
   to fill `created_by` and `updated_by` without every form passing the
   user down. A worker task has no request, so those fields stay empty
   there unless the task calls `set_current_user()`.
3. **`HtmxLoginRedirectMiddleware`** (`apps/accounts/middleware.py`). Runs
   on the way out: when a request carries `HX-Request: true`, the user is
   anonymous and the response is a 302, it is replaced by a 200 with
   `HX-Redirect` set to the same location. HTMX follows that with a full
   navigation, so an expired session takes the page to the sign-in form
   instead of swapping the sign-in form into a list.
4. **`PermissionMiddleware`** (`apps/accounts/middleware.py`). First,
   for every request, it answers 404 on the pages of an optional
   integration that is not set up: `AI_PATTERN` (the AI tab, the drafts
   companion, intake assessment and chat) without an AI key,
   `CASELAW_PATTERN` (saved case law and the cluster viewer) without a
   CourtListener token; see
   [AI is optional](ai/context.md#ai-is-optional). Then, for a
   signed-in user who is not an admin, it refuses with 403: `/admin/`;
   the `ADMIN_ONLY_PATHS` (the Users, Permissions, Firm, Contacts, Matters
   and Tasks settings pages); any path in `PERMISSION_PATHS` whose flag
   the user lacks (`/invoicing/` and `/reports/` by prefix, `/intakes/`
   and the intake-emails settings); and the `PERMISSION_PATTERNS`, which
   gate matter-scoped paths such as `/matters/<id>/rates` and `/ledger`
   (`perm_financial`) and saved case law and the case viewer
   (`perm_research`). Its
   `process_view()` then enforces matter membership for everything under
   `/case/`: `user_may_use_route()` in `apps/accounts/access.py` resolves
   the matter from whichever id the URL names (document, fact,
   conversation, and so on, through `MATTER_LOOKUPS`) and refuses a user
   limited to assigned matters. The comment in the class states the rule:
   hiding a tab is not a gate; the URL has to refuse too. `/matters/` and
   `/notes/` views carry their own checks. The flags and what they open
   are in the [permissions matrix](../../reference/permissions.md).
5. **`HistoryRequestMiddleware`** (`simple_history`). Attaches the
   request user to the history rows written by models with
   `HistoricalRecords()`.

## Storage

`STORAGE_BACKEND` selects the default storage: `local` is
`FileSystemStorage` under `MEDIA_ROOT` (`media/` in the checkout), `s3`
is `django-storages`' `S3Storage` configured from the `DIGITAL_OCEAN_*`
variables, with `AWS_QUERYSTRING_AUTH` on so any URL the storage hands
out is signed and expiring. Any other value raises
`ImproperlyConfigured` at startup. The comment in settings records the
choice: local is the default on purpose so a checkout runs without cloud
credentials, and production never exposes `MEDIA_ROOT` through a public
URL. Code reads and writes files only through a `FieldFile` or
`default_storage`, so the two backends are interchangeable; a path on
disk is wrong in either. The operator's setup and the switch between
backends are in [File storage](../../admin/integrations/storage.md).

## Email

Outgoing mail is Django's mail framework over the backend chosen by
`EMAIL_BACKEND`: `console`, `locmem` or `smtp`, defaulting to `console`
under `DEBUG` and `smtp` otherwise. The SMTP settings are the standard
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER` and
`EMAIL_HOST_PASSWORD`; `EMAIL_TIMEOUT` (default 10 seconds) exists
because the sign-in code is sent during the request, and without it a
blocked port hung the login page until gunicorn killed the worker.

Three from addresses: `SERVER_EMAIL` for error reports to `ADMINS`,
`DEFAULT_FROM_EMAIL` for the application's mail, and
`BILLING_FROM_EMAIL` for client-facing billing mail. `utils/mail.py`
builds the display names (`firm_from_email()`, `billing_from_email()`,
the matching `*_reply_to()` helpers), embeds the firm logo by content id
(`attach_firm_logo()`) and inlines CSS for HTML mail
(`render_inlined()`). The senders are: the sign-in code
(`apps/accounts/utils.py`), invoices and payment requests
(`apps/invoicing/invoices/functions/send_invoice.py`,
`apps/invoicing/requests/send.py`), intake replies and client forms
(`apps/intakes/send.py`, `apps/intakes/client_forms/send.py`), the daily
digest (`apps/tasks/digest.py`), and `mail_admins()` from payment
reconciliation (`apps/invoicing/pay/reconcile.py`) when a settled payment
reverses and a person has to look.
Inbound mail does not use SMTP: Mailgun posts to a webhook, described in
[Email and intakes](email-and-intakes.md).

## Logging

`LOGGING` has one format and two handlers: the console (which gunicorn
captures into `logs/error.log` and the worker into the journal) and
`logs/django.log`, both at `WARNING`. The `logs/` directory is created by
settings at import. `django.security.DisallowedHost` goes to a null
handler because scanners with bad `Host` headers were filling the log
with tracebacks. There is no per-app logging configuration: a module
takes `logging.getLogger(__name__)` and inherits the root. Where the
files are and how they rotate is in [Monitoring](../../admin/monitoring.md).

## Health

`config/health.py` answers three URLs, all `require_safe`, none
authenticated, all with `Cache-Control: no-store`:

- `/health/live/` returns `ok` without touching anything.
- `/health/ready/` runs `SELECT 1` and returns 503 when the database does
  not answer.
- `/health/worker/` has no port to probe on the worker, so it reads the
  worker's effect: a running worker keeps every schedule's `next_run` in
  the future. A schedule overdue by more than `WORKER_STALE_AFTER` (five
  minutes), or no schedules at all (`setup_schedules` not run), is 503.

`config/tests/test_health.py` covers all three.

## The base templates

- `templates/base.html` is the application shell: every stylesheet
  (linked through the `static_v` tag from
  `apps/management/templatetags/cache_buster.py`, which appends the
  file's modification time), the theme bootstrap script that sets
  `data-theme` before first paint, the sidebar, the mobile top bar, the
  toast container, the modal containers, and the vendor scripts. The CSRF
  token is set once as `hx-headers` on `<body>`, so no HTMX form carries
  it. Pages extend it and fill `content` and, optionally, `body_class`.
- `templates/base-minimal.html` is the same head without the sidebar, for
  pages shown outside the shell: the public payment and intake-form
  pages, the notes editor and the AI prompt windows. It exposes `title`
  and `favicon` blocks.
- `templates/registration/base.html` is a third, smaller head that the
  sign-in, code and password reset pages under `templates/registration/`
  extend. It is not derived from the other two, so a stylesheet added to
  `base-minimal.html` does not reach the auth pages.
- The error pages `400.html`, `403.html`, `404.html` and `500.html` are
  at the top of `templates/`.

## `utils/`: what each guard is for

- **`safe_markdown.py`**. Notes on intakes and tasks render Markdown that
  may have come from outside the firm (a forwarded email, a client's
  answers, a model's summary). Python-Markdown passes raw HTML through,
  so `render_markdown()` adds `UntrustedTextExtension`, which deregisters
  the HTML block and inline patterns (markup becomes text) and runs a
  tree processor that drops any `href` whose scheme is not http, https,
  mailto or tel (after stripping the control characters browsers ignore
  in a scheme) and turns every image into a link to itself, so opening a
  note fetches nothing from a third party. `<br>` alone is restored
  afterwards, for the client-form report's table cells. Use it for any
  Markdown that is marked `|safe`.
- **`safe_json.py`**. `json_for_script()` is `json.dumps` with `<`, `>`,
  `&` and the two Unicode line separators escaped as `\uXXXX`, for values
  assigned inside an existing `<script>` (a highlight's text, selected
  from a PDF, could otherwise contain `</script>`). Django's
  `json_script` filter does the same for a standalone element.
- **`toasts.py`**. `add_toast()` and the `toast_success()` family set an
  `HX-Toast` header on a response; a second call on the same response
  stacks the rest in `HX-Toasts`. `static/js/toasts.js` renders both. Errors are sticky by default,
  `mobile_only` marks a toast the desktop page already shows by other
  means.
- **`signing.py`**. The signed, expiring tokens for the public pages,
  built on `django.core.signing` with a salt per purpose, so a payment
  token cannot open an intake form. The invoice token names the invoice
  by `uuid`, never by its sequential id.
- **`ratelimit.py`**. A fixed-window counter per client IP in the default
  cache for the public pages. Its docstring is honest about the limits:
  the cache is per process, so an N-worker deployment allows N times the
  stated limit, and the token, not the limiter, is the access control.
  `client_ip()` takes the last address in `X-Forwarded-For`, the one
  nginx appended, so a caller cannot choose its own identity.
- **`links.py`**, **`mail.py`**, **`models.py`**, **`middleware.py`**: see
  above.

## `config/tests/`

| Test module | Pins |
|---|---|
| `test_health.py` | The three health endpoints, including the overdue-schedule and no-schedule cases. |
| `test_media_security.py` | Local media is unrouted in production, routed under `runserver`, never mapped under S3; the logo exception; the document endpoints require a login. |
| `test_ratelimit.py` | `client_ip()` cannot be steered by a forged header. |
| `test_safe_markdown.py` | Raw HTML is text, no link may point at script, images fetch nothing. |
| `test_docs_reference.py` | The generated reference pages and `.env.example` are current. |

## Things that bite

- **Settings are read once, per process.** The web application and the
  worker each read `config/.env` at start. Editing it and restarting one
  of them leaves the two running different settings.
- **Templates are cached when `DEBUG` is off.** The cached loader keeps a
  parsed template for the life of the process, so a checkout that moves
  to a new commit without a restart serves old templates against new
  views (the October 2026 `NoReverseMatch` on `/` was this). Restart
  gunicorn and the worker after any deploy.
- **The default cache is per process.** Anything that must be seen by
  another gunicorn worker, or by the worker process, cannot live in
  `CACHES["default"]`. The AI run status has its own database cache for
  exactly this reason; rate-limit counters accept the imprecision.
- **`ENV` and `DEBUG` are independent.** A machine with `DEBUG=True` and
  `ENV=prod` keeps sessions in the database and shows no development
  banner. Code that must know which environment it is in tests `ENV`.
- **`AuditMixin` depends on the request thread.** `created_by` is filled
  from the thread local, so a model saved from a worker task or a
  management command records no user unless the caller sets one.
- **The permission middleware matches paths, not views.** A new page that
  should be gated by a flag needs its prefix or pattern added to
  `PermissionMiddleware`, and a new kind of id in a `/case/` URL needs a
  line in `MATTER_LOOKUPS`, or membership is not enforced for it.
- **Local media is not served in production.** A template that builds a
  `media/...` URL for anything but the firm logo works under `runserver`
  and 404s on a server. Serve the file through a view.

## Related

- [Configuration](../../admin/configuration.md),
  [File storage](../../admin/integrations/storage.md),
  [Email](../../admin/integrations/email.md),
  [Monitoring](../../admin/monitoring.md) in the operator guide.
- [Environment reference](../../reference/environment.md),
  [permissions matrix](../../reference/permissions.md).
- [Architecture](../architecture.md),
  [Identity and access](identity-and-access.md),
  [Operations](operations.md).
