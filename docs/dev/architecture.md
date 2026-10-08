# Architecture

Kosmos is one Django project (`config/`) over twenty-one apps under
`apps/`, rendered server-side and driven in the browser by HTMX and
Alpine. One PostgreSQL database holds the records, the search indexes, the
task queue and the AI status cache. A second process, the Django-Q worker,
runs queued and scheduled work. This page is the map: where things are,
how a request moves, and where state and background work live. Each
subsystem has its own page under `subsystems/`.

## The apps

Every app in `apps/` is listed in `INSTALLED_APPS` in `config/settings.py`
and mounted in `config/urls.py`. They are grouped here the way the
subsystem pages group them.

| Group | Apps | What they hold |
|---|---|---|
| [Platform and config](subsystems/platform-and-config.md) | `config/`, `utils/`, `apps/management` | Settings, URL root, middleware, health checks; the shared helpers (`utils/`); the session-held filter, selection and pagination helpers, the schedule registry and the `static_v` template tag. |
| [Identity and access](subsystems/identity-and-access.md) | `apps/accounts` | `CustomUser` with its `perm_*` flags and `is_admin`, the emailed sign-in code, `access.py` (matter membership) and the two project middlewares. |
| [Matters](subsystems/matters.md) | `apps/matters`, `apps/contacts`, `apps/folders` | Matters, proceedings, rates, ledger, settlement; contacts and relationships; the contact folders (`Folder` is also the task folder). |
| [Tasks and calendar](subsystems/tasks-and-calendar.md) | `apps/tasks`, `apps/checklists`, `apps/calendar`, `apps/dash` | Tasks and the daily digest; checklist templates; events and the Google Calendar sync; the dashboard. |
| [Time and billing](subsystems/time-and-billing.md) | `apps/activity`, `apps/invoicing`, `apps/reports` | Time, expense and flat-fee entries with their categories; invoices, credits, payment requests; the reports. |
| [Trust and payments](subsystems/trust-and-payments.md) | `apps/trust`, `apps/invoicing/pay`, `apps/invoicing/processors` | The trust ledger; the public payment page, the processor adapters (LawPay, Stripe, Confido, a fake for tests) and webhook reconciliation. |
| [Case building](subsystems/case-building.md) | `apps/case`, `apps/drive`, `apps/search` | Documents and OCR, highlights, facts, witnesses, labels, the case search tab and the saved case law; the Google Drive mirror; the global search modal. |
| [AI](subsystems/ai/context.md) | `apps/case/ai` | The context builders, the chat surfaces, the agent tool loop (with its CourtListener research tools), the semantic index. |
| [Notes and drafts](subsystems/notes-and-drafts.md) | `apps/notes`, `apps/drafts` | The notes editor, folders and library; draft links and the LibreOffice companion (`companion_src/`). |
| [Email and intakes](subsystems/email-and-intakes.md) | `apps/mail`, `apps/intakes` | Gmail sync onto matters; intakes, the inbound Mailgun webhook, the client forms. |
| Settings | `apps/settings` | One package per Settings page (`firm/`, `users/`, `permissions/`, `appearance/`, `integrations/`, `claude/`, and so on) and the `Firm` record. |

Three apps are thin: `apps/dash`, `apps/reports` and `apps/search` have
no models of their own (`apps/search` holds the watson registrations in
`search_config.py`, the search modal's views and the `search/api/` JSON
endpoint in `api.py` that the MCP server's `search_kosmos` tool calls).
None of
the directories under `apps/` is vestigial: every one is installed and
routed. There is no `billing`, `lab` or `research` app; billing lives in
`apps/invoicing` and case-law research in the agentic chat's tools
(`apps/case/ai/agent_tools.py`) over the CourtListener client in
`apps/case/courtlistener.py`. Three packages have no `urls.py`:
`apps/mail` and `apps/drafts` have their views mounted from
`apps/case/urls.py`, and `apps/drive` has no views at all (it is driven
by signals, the worker and management commands).

## `config/`

| File | What it does |
|---|---|
| `config/settings.py` | Reads `config/.env` through `django-environ`, defines `Q_CLUSTER`, the two caches, storage, email and logging. Explained in [Platform and config](subsystems/platform-and-config.md). |
| `config/urls.py` | The health endpoints, the sign-in views, then one `include()` per app at the root, including the two public, tokenized URL sets (the payment page under `apps/invoicing/pay/urls.py` and the client intake form under `apps/intakes/client_forms/public_urls.py`). |
| `config/health.py` | `/health/live/`, `/health/ready/` and `/health/worker/`. |
| `config/context.py` | Two context processors: `env` (the `ENV` value, which the templates use to show the development banner) and `integrations` (lazy `ai_enabled` and `caselaw_available`, which hide the optional AI and saved case-law surfaces). |
| `config/helpers.py` | Small utilities used across apps: `normalize_phone()`, `dictfetchall()`, `MultipleOrderingFilter` for `django-filter`, and the `dump*` debugging helpers. |
| `config/tests/` | Tests for the health endpoints, media routing, rate limiting, safe Markdown and the generated reference pages. |

The middleware order is fixed in `MIDDLEWARE`: Django's own stack, then
`DailyDashCheckMiddleware`, `CurrentUserMiddleware`,
`HtmxLoginRedirectMiddleware`, `PermissionMiddleware` and
`simple_history`'s `HistoryRequestMiddleware`. What each does is on the
[platform page](subsystems/platform-and-config.md#middleware).

## The two shells

A user works in one of two shells, both wrapped by `templates/base.html`.

**The Practice shell** is the firm-wide one: `templates/sidebar.html` lists
Dash, Matters, Calendar, Tasks, Contacts, Activity, Library and, by
permission flag, Invoicing, Intakes and Reports, with Search, Settings and
Shortcuts below. The sidebar's list is `hx-boost`ed with
`hx-target="#main-content"` and `hx-select="#main-content"`, so a click
fetches the full page and swaps only the content column; the sidebar
itself is never re-rendered by navigation. Which item is active comes
from the `app` context variable each view sets.

**The matter workspace** opens from a matter and has two modes, switched
by the pills in `templates/matters/includes/mode-pills.html`:

- **Detail**, under `/matters/<id>/...`, is the matter's record: Overview,
  Contacts, Rates, Activity, Events, Tasks, Proceedings, Settlement and
  Ledger (`templates/matters/includes/detail-nav.html`).
- **Case**, under `/case/<id>/...`, is the matter's working file:
  Documents, Highlights, Timeline, Witnesses, Notes, Emails, Labels,
  Search, AI and Research (`templates/case/includes/case-nav.html`).

Both modes extend `templates/matters/matter-base.html`, which places the
matter header (`matters/includes/header.html`: the matter switcher, the
mode pills, the action buttons) above a `#mode-content` block. Switching
mode swaps that block through `matters:mode-content` or
`case:mode-content`; switching tab inside a mode swaps `.detail-body`
through `matters:tab-content` or `case:tab-content`. The tab views
(`apps/matters/views.py` and `apps/case/views.py`) gather the tab's data
through one `get_<tab>_data()` function per tab, shared by the full-page
view and the partial, so a tab renders the same either way. The case
shell remembers the last matter and the last tab per matter in the
session (`last_viewed_matter`, `case_tab_<id>`), which is how `/case/`
reopens where the user left off.

The templates directory follows the shells: `templates/base.html` and
`templates/sidebar.html` are the Practice shell; `templates/matters/` and
`templates/case/` are the workspace; every other app has a directory of
its own. `templates/components/` holds the pieces several pages include:
the form-field renderers (`form-fields-template*.html`, selected through
`FORM_RENDERER` in settings), the HTMX modal shell, the brand marks and
gradients, the user chips and the format toolbar. `templates/base-minimal.html`
is the no-sidebar base for the sign-in pages, the public payment and
intake-form pages, the notes editor and the AI prompt windows.

## How a request moves

A typical page is rendered once in full and then updated in parts.

1. **Full render.** The browser requests `/tasks/`. `tasks_index` in
   `apps/tasks/views.py` reads the user's filter, selection and page from
   the session, builds the list, and renders `tasks/tasks.html`, which
   extends `base.html` and includes the list partial.
2. **Partial swap.** Every control on the page is an `hx-get` or
   `hx-post` to a view that renders only the partial it changes: a row, a
   list, a modal (`#htmx-modal-container`, which `templates/modals.html`
   provides). Alpine handles the purely client-side state (open menus,
   modal visibility) through the components in
   `static/js/alpine-components.js`.
3. **Events.** A view that changed data sets `HX-Trigger` on its
   response (`tasksListChanged`, `eventsChanged`, `wipChanged`, and so
   on). Containers that depend on that data listen with
   `hx-trigger="tasksListChanged from:body"` and re-fetch themselves, so
   a modal that saves a task closes and the list behind it refreshes
   without the view knowing about the list. The trigger names are
   constants in the views (`TASKS_TRIGGER` in `apps/tasks/views.py`).
4. **Toasts.** `utils/toasts.py` adds an `HX-Toast` header to any
   response; `static/js/toasts.js` shows it.
5. **Logged out mid-page.** A session that expires makes a partial request
   receive a login redirect; `HtmxLoginRedirectMiddleware` turns that into
   an `HX-Redirect` so the whole page goes to the sign-in form instead of
   a form being swapped into a table cell.

The patterns, including idiomorph swaps and the `hx-swap-oob` navigation
updates, are on the [HTMX and Alpine](conventions/htmx-alpine.md) page.

## Where state lives

- **The database** holds everything durable, including the Django-Q queue
  and schedules, the watson search index, the pgvector chunks, the
  `simple_history` tables, and the `ai_status_cache` table.
- **The session** holds the user's working state: list filters
  (`FilterManager` in `apps/management/filter_manager.py`), multi-select
  selections (`apps/management/selection.py`), the current page
  (`apps/management/pagination.py`), the user chips, and the last matter
  and tab of the workspace. The session is saved on every request
  (`SESSION_SAVE_EVERY_REQUEST`) and lasts eight weeks. See
  [Session state](conventions/session-state.md).
- **The per-process cache** (`CACHES["default"]`, LocMem) holds
  CourtListener opinion payloads and the public-page rate-limit counters.
  It is private to each gunicorn worker.
- **The browser** keeps the theme, the sidebar collapsed flag and similar
  preferences in `localStorage` (`static/js/theme.js`, `sidebar.js`).

## Background work

Two mechanisms run work outside a request, and they are not
interchangeable.

**The Django-Q worker** (`python manage.py qcluster`, the `qcluster.service`
unit in production) runs everything that is queued with
`django_q.tasks.async_task()` and the recurring schedules in
`apps/management/schedules.py`: OCR, Drive, Gmail and Calendar sync,
document and note summaries, semantic re-indexing, payment webhook
reconciliation, the daily digest, the chat purge. The worker is configured by `Q_CLUSTER` in
settings and explained on the [operations page](subsystems/operations.md).

**In-process daemon threads** run the interactive AI chats. `send_message`
in `apps/case/ai/views.py` saves the user's message, seeds a status entry
and starts `threading.Thread(target=process_ai_request, daemon=True)`
(`apps/case/ai/tasks.py`) inside the gunicorn worker that took the
request; the intake chat (`apps/intakes/chat.py`) does the same. The browser polls `case:ai-status`
every second. The code does not record why chats run on threads rather
than the queue; the consequence it does record is that a restart of the
web process ends every reply in flight, and the status cache below exists
to report that honestly.

The two meet in **the status cache**. `apps/case/ai/status.py` defines
`status_cache`, the `ai_status` cache from settings: a `DatabaseCache`
over the `ai_status_cache` table, created by `manage.py createcachetable`
and not by a migration. It has to be in the database because production
runs several gunicorn workers and a poll usually lands in a worker other
than the one running the thread; the per-process LocMem cache gave every
worker a private view and the poller fabricated "server restarted"
replies (recorded in the docstring, 2026-08-17). Liveness is by TTL:
`RunHeartbeat` re-touches the entry every 30 seconds while the thread's
process lives, so a deploy that kills the process lets the entry expire
and the poller reports the interruption within `RUNNING_TTL`.

## Storage

Uploaded files go through Django's storage API, never to a path. The
backend is chosen by `STORAGE_BACKEND` in `config/.env`: `local` writes
under `media/` in the checkout, `s3` uses `django-storages` against an
S3-compatible bucket (the settings are named `DIGITAL_OCEAN_*`). Nothing
under `media/` is routed in production except `media/company/` (the firm
logo); documents are streamed by `serve_document` in
`apps/case/documents/views.py` after the access checks. The routing
rules are the two functions at the bottom of `config/urls.py`, and
`config/tests/test_media_security.py` pins them.

## Search

Two indexes, both in PostgreSQL:

- **Keyword** search is `django-watson`. Models register in
  `apps/search/search_config.py` (matters, contacts, intakes) and
  `apps/case/search_config.py` (documents, highlights, facts, notes,
  emails). The case search tab (`apps/case/search/views.py`) calls
  `watson.search()`; the agent's `search_materials` tool
  (`apps/case/ai/agent_tools.py`) queries `watson_searchentry` directly
  with `websearch_to_tsquery`, scoped to one matter. `Document` and
  `Highlight` also carry their own `SearchVectorField`, kept current by
  the OCR task and `update_search_vectors`.
- **Semantic** search is `apps/case/ai/semantic.py`: material text is
  chunked, embedded with Gemini (`apps/case/ai/embeddings.py`, 768
  dimensions) and stored as `MaterialChunk` rows with a pgvector column
  and an HNSW index. `semantic_entries()` returns cosine neighbours, and
  the agent tool fuses them with the keyword hits. Saves enqueue
  re-indexing on the worker when `SEMANTIC_AUTO_INDEX` is on and a Gemini
  key is configured; `build_semantic_index` backfills. Without a Gemini
  key semantic results are simply empty and search is keyword-only.

## `static/`

| Path | What it is |
|---|---|
| `static/js/main.js` | Page-wide behaviour: the confirm-link handler, CSRF helper, clipboard, the space-bar leader key and the command palette, matter switcher and nav switcher it opens. |
| `static/js/alpine-components.js` | The `Alpine.data()` components: `dropdown`, `modal`, `confirmModal` and the chart toggles. |
| `static/js/toasts.js`, `htmx-focus.js`, `sidebar.js`, `theme.js`, `nav-layout.js` | The shell: toasts, focus after swaps, the sidebar, themes and the painted favicon, the horizontal layout. |
| `static/js/<app>.js`, `static/js/notes/` | Per-app scripts; the notes editor is split into modules under `notes/` and loaded as ES modules. |
| `static/js/vendor/tiptap.bundle.js` | The notes editor's Tiptap build (`@tiptap/*` 2.27.2, bundled with esbuild). Its build sources are not in the repository: the bundle was rebuilt by hand and committed (2026-08-15, "table support with pipe-markdown round-trip"), and the `build.mjs` that produced it was retired. To add an extension, rebuild the bundle the same way and commit the result. |
| `static/css/palette.css`, `colors.css` | The colour ramps and the semantic tokens for the seven themes; see [CSS theming](frontend/theming.md). |
| `static/css/*.css`, `static/css/apps/` | One stylesheet per component and per app, every one linked from `base.html` through `static_v`, which appends the file's modification time so a changed file is fetched again. |
| `static/pdfjs/` | The PDF.js viewer, refreshed by `scripts/update_pdfjs.py`. |

HTMX, idiomorph, Alpine, Flatpickr, FullCalendar, Chart.js, Dropzone and
SortableJS are loaded from CDNs in `base.html`, not vendored. In
production nginx serves `/static/` from the checkout with a 30-day cache,
except `/static/js/`, which is `no-cache` because the ES module imports
are bare paths that `static_v` cannot version (`deploy/nginx/kosmos.conf`).

## The deployment

```
   browser
      |  HTTPS
      v
   nginx  (deploy/nginx/kosmos.conf: TLS, rate limits, /static/)
      |  unix socket /run/law.sock
      v
   gunicorn  (law.service, N workers)       qcluster  (qcluster.service)
   Django: config.wsgi                      Django-Q worker, 2 task slots
      |  AI chat runs: daemon threads           |  queued tasks + schedules
      |                                         |
      +----------------+------------------------+
                       |
                       v
                  PostgreSQL
     records, watson + pgvector indexes, django_q queue,
     ai_status_cache, sessions (prod), simple_history
                       |
         +-------------+--------------+
         v                            v
   object storage               external services
   STORAGE_BACKEND=s3           Google (Calendar, Contacts, Drive, Gmail)
   (or media/ on disk)          Anthropic and Gemini (chat, summaries,
                                  embeddings)
                                CourtListener (research, citations)
                                LawPay, Stripe, Confido (payments,
                                  webhooks back to /webhooks/)
                                Mailgun (SMTP out; inbound route posts
                                  intake email to the webhook)
                                LibreOffice (local, headless; drafts)
```

Both Django processes read `config/.env` themselves, so the systemd units
carry no environment file, and a change to `.env` needs both restarted.
The templates in `deploy/` are rendered by `scripts/install.sh --prod`;
the operator's view of the same layout is in
[Install](../admin/install.md) and [Background worker](../admin/worker.md).

## Related

- [Platform and config](subsystems/platform-and-config.md),
  [Operations](subsystems/operations.md).
- [HTMX and Alpine](conventions/htmx-alpine.md),
  [Session state](conventions/session-state.md),
  [Testing](conventions/testing.md).
- [Development environment](setup.md).
