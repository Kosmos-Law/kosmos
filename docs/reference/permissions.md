# Permissions matrix

What each role and permission flag gates, which routes need no sign-in, and
how the token-authenticated APIs are scoped. How to set these is in
[Users and permissions](../admin/users.md).

Every route requires a signed-in session (`@login_required` on the view)
unless it is listed under
[Routes that need no sign-in](#routes-that-need-no-sign-in) or
[Token-authenticated APIs](#token-authenticated-apis). There is no global
sign-in middleware.

## Roles and flags

All are fields on `CustomUser`
([`apps/accounts/models.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/accounts/models.py)).

| Name in Settings | Field | Default for a new user | Notes |
|---|---|---|---|
| Role: Admin | `role = "ADMIN"` | `USER` (`ADMIN` from `createsuperuser`) | `is_admin` is true only for this role. An admin passes every check on this page whatever the flags say, except the daily digest row below. |
| Role: User | `role = "USER"` | yes | Subject to the five flags. |
| All Matters | `perm_all_matters` | on | Off limits the user to matters they are a member of (`Matter.members`). |
| Financial | `perm_financial` | on | |
| Intakes | `perm_intakes` | on | |
| Reports | `perm_reports` | off | The one switch that starts off: the reports show the whole firm's figures. An administrator turns it on for each user who needs it. |
| Research | `perm_research` | on | |
| (not in Settings) | `is_staff`, `is_superuser` | off (on from `createsuperuser`) | Django's own flags. Needed for `/admin/` in addition to the Admin role. |
| Status | `is_active` | on | Off refuses sign-in, ends existing sessions and rejects the user's API token. |

## Path rules (`PermissionMiddleware`)

Source:
[`apps/accounts/middleware.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/accounts/middleware.py).
The rules run only for a request that is signed in. A request with no
session passes through untouched and is handled by the view (normally a
redirect to `/accounts/login/`). A blocked request gets HTTP 403 with an
empty body, not a redirect.

Rules 1 to 4 test the request path before the URL is resolved and are
skipped for an admin. Rule 5 runs once the URL is resolved, from the ids in
it.

| Order | Rule (list in the source) | Path | Who passes |
|---|---|---|---|
| 1 | Prefix | `/admin/` | Admin role only |
| 2 | Prefix (`ADMIN_ONLY_PATHS`) | `/settings/users/` | Admin role only |
| 2 | Prefix (`ADMIN_ONLY_PATHS`) | `/settings/permissions/` | Admin role only |
| 2 | Prefix (`ADMIN_ONLY_PATHS`) | `/settings/firm/` | Admin role only |
| 2 | Prefix (`ADMIN_ONLY_PATHS`) | `/settings/contacts/` | Admin role only |
| 2 | Prefix (`ADMIN_ONLY_PATHS`) | `/settings/matters/` | Admin role only |
| 2 | Prefix (`ADMIN_ONLY_PATHS`) | `/settings/tasks/` | Admin role only |
| 3 | Prefix (`PERMISSION_PATHS`) | `/invoicing/` | Admin, or `perm_financial` |
| 3 | Prefix (`PERMISSION_PATHS`) | `/intakes/` | Admin, or `perm_intakes` |
| 3 | Prefix (`PERMISSION_PATHS`) | `/settings/intake-emails/` | Admin, or `perm_intakes` |
| 3 | Prefix (`PERMISSION_PATHS`) | `/reports/` | Admin, or `perm_reports` |
| 4 | Pattern (`PERMISSION_PATTERNS`) | `/matters/<id>/rates` and `/matters/<id>/ledger`, alone or followed by `/…` | Admin, or `perm_financial` |
| 4 | Pattern (`PERMISSION_PATTERNS`) | `/case/research/…`, `/case/<id>/research/…` and the tab-switch address `/case/<id>/tab/research/` | Admin, or `perm_research` |
| 5 | Matter membership (`MATTER_SCOPED_PREFIXES`, `process_view`) | Everything under `/case/` | Admin, `perm_all_matters`, or a member of every matter the URL's ids belong to. The lookup is set out under Matter membership below. |

The two patterns as written in the source:

```
^/matters/\d+/(rates|ledger)(/|$)
^/case/(\d+/)?(tab/)?research/
```

What sits under each path:

| Path | Features |
|---|---|
| `/admin/` | The Django admin. Django itself also requires `is_active` and `is_staff`. `/admin/login/` is not a form: see [Routes that need no sign-in](#routes-that-need-no-sign-in). |
| `/settings/users/` | User list, create, edit, change role, switch status, toggle a permission, matter assignments. |
| `/settings/permissions/` | The permissions matrix page. |
| `/settings/firm/` | Firm details and logo. |
| `/settings/contacts/` | Contact roles, groups and relationship types. |
| `/settings/matters/` | Practice areas. |
| `/settings/tasks/` | Task settings. |
| `/invoicing/` | Invoices, unbilled work, payments, credits, collection, payment requests, and the trust ledger (`/invoicing/trust/`). |
| `/intakes/` | Intakes, their notes and chat, and the intake form builder (`/intakes/forms/`). |
| `/settings/intake-emails/` | Intake email templates. |
| `/reports/` | All reports. |
| `/matters/<id>/rates…` | A matter's Rates page and its list, add, edit and delete routes. |
| `/matters/<id>/ledger…` | A matter's Ledger tab, list and PDF. |
| `/case/research/…`, `/case/<id>/research/…` | Research searches, history, review, abstracts, saved case law lists, briefs and citation checks. |
| `/case/` | The case workspace: documents and the viewer, highlights, timeline facts, witnesses, labels, notes, emails, case search, AI chats, drafts and research. |

## Gates checked in views

"Blocked" is what a signed-in user who fails the check receives.

### Matter membership (`perm_all_matters`)

A user passes when they are an admin, have `perm_all_matters`, or are in the
matter's `members`.

| Gate | Where it applies | Location | Blocked |
|---|---|---|---|
| `PermissionMiddleware.process_view`, `user_may_use_route` | Every route under `/case/`, by the ids in its URL (table below) | `apps/accounts/middleware.py:84`; [`apps/accounts/access.py:100`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/accounts/access.py) | 403 |
| `matter_access_required` | Views under `/matters/<id>/…` that take the matter id: overview, edit, tab content, contacts, events, tasks, activity, timeline, proceedings, categories, settlement, rates, ledger, work status | `apps/accounts/access.py:9`; decorators in `apps/matters/**/views.py` | 403 |
| `matter_access_required` | `/case/select-matter/<id>/`, `/case/<id>/mode-content/` (also covered by the middleware) | `apps/case/views.py:85`, `:99` | 403 |
| `filter_matters_for_user` | Matter list, quick search, open-matter switcher JSON, open-matter dropdown and steppers on the matter detail page | `apps/matters/get_matter_list.py:36`; `apps/matters/views.py:140`, `:648`; `apps/matters/templatetags/matter_tags.py:14` | Matter not listed |
| `filter_matters_for_user` | Matter switcher in the case workspace | `apps/case/views.py:113`, `:137`, `:245`; `apps/case/documents/get_document_data.py:26` | Matter not listed |
| `filter_matters_for_user` | Matter choices in the task, time, expense, flat-fee, document and case-note forms | `apps/tasks/forms.py:69`, `:132`; `apps/activity/time/forms.py:75`; `apps/activity/expenses/forms.py:64`; `apps/activity/flat_fees/forms.py:60`; `apps/case/documents/forms.py:64`; `apps/case/notes/forms.py:28` | Matter not offered |
| `assigned_matters` filter | Time, expense and flat-fee lists under `/activity/` | `apps/activity/time/get_time_data.py:23`; `apps/activity/expenses/get_expenses_data.py:23`; `apps/activity/flat_fees/get_flat_fees_data.py:22` | Entries not listed |
| `has_matter_access` | Every `/notes/<id>/…` endpoint, for a note that belongs to a matter | `apps/notes/views.py:1003` (`_get_note`) | 404 |
| `filter_matters_for_user` | Notes editor tree, palette and search scopes | `apps/notes/views.py:802`, `:980`, `:1265`, `:1279` | Notes not listed |
| `has_matter_access` | Case note "Edit Details" modal (also covered by the middleware) | `apps/case/notes/views.py:148` | 404 |
| `filter_matters_for_user` | Matters, proceedings and matter notes in in-app search results | `apps/search/views.py:152` | Not listed |
| `entries_for_user` | Time, expense and flat-fee CSV exports, and the entries a bulk change touches | `apps/activity/access.py:23` | Entries left out |
| `entry_for_user` | Opening, saving, deleting or toggling one time, expense or flat-fee entry by its id | `apps/activity/access.py:30` | 403 |
| `has_matter_access` | The rate, trust-available and flat-fee-amount lookups behind the entry forms | `apps/activity/time/views.py`, `apps/activity/flat_fees/views.py` | 403 |
| `matters_for_entry_form` | Matter choices in the entry forms and in the bulk "move to matter" menus | `apps/activity/access.py:48` | Matter not listed |
| `assigned_matters` filter | "Upcoming Events" on the dashboard (events on no matter are shown to everyone) | `apps/dash/views.py:41` | Events not listed |
| `filter_matters_for_user` | Dashboard matter lists, AI agenda matter list | `apps/dash/views.py:162`, `:311`; `apps/dash/agenda.py:110`, `:201` | Matter not listed |
| `filter_matters_for_user`, `has_matter_access` | `/case/` landing redirect | `apps/case/views.py:58`, `:63` | Redirects to an accessible matter |
| `perm_all_matters` only (role not consulted) | Daily digest email content | `apps/tasks/digest.py:47` | Items for other matters omitted |
| Token APIs | See [Token-authenticated APIs](#token-authenticated-apis) | | 404 |

How the middleware finds the matter of a `/case/` route. Each URL keyword
names a record, and the record leads to a matter (`MATTER_LOOKUPS` and
`OBJECT_TYPE_KEYS`, `apps/accounts/access.py:39`, `:63`):

| URL keyword | Record | Matter taken from |
|---|---|---|
| `matter_id` | The matter itself | |
| `document_id` | Document | The document |
| `highlight_id` | Highlight | Its document, or its case law |
| `caselaw_id` | Saved case law | The case law |
| `fact_id` | Timeline fact | The fact |
| `witness_id` | Witness | The witness |
| `label_id` | Label | The label |
| `note_id` | Note | The note |
| `conv_id` | AI conversation | The conversation |
| `message_id` | AI message | Its conversation |
| `email_id` | Synced email | The email |
| `query_id` | Research query | The query |
| `result_id` | Research result | Its query |
| `verification_id` | Citation check | Its result's query |
| `brief_id` | Case brief | The brief |
| `object_type` with `object_id` | Label and witness pickers: a `document`, `highlight`, `fact`, `note`, `caselaw` or `witness` | As for that kind of record |

| Case | Result |
|---|---|
| Admin, or `perm_all_matters` | Passes. Nothing is looked up. |
| The URL names several records | The user must be a member of every matter found. |
| An id matches no record | Not refused here. The view answers 404. |
| The record has no matter (a library note, an intake chat) | Not refused here. |
| The URL carries none of these keywords (`/case/`, `/case/no-matter/`) | Not refused here. |
| A request with no session (including the token APIs under `/case/api/` and `/case/drafts/companion/api/`) | Not checked here. The view or its token check decides. |

Outside `/matters/<id>/` and `/case/`, membership is checked in the view,
through each application's own access module:

| Area | What a restricted user gets | Location |
|---|---|---|
| Tasks (`/tasks/…`, the matter Tasks tab, the daily digest) | Tasks on their matters and tasks on no matter; another matter's task is refused (403); the form's matter list is theirs | `apps/tasks/access.py` |
| Calendar (`/events/…`, the matter Events tab, the calendar feed) | Events on their matters and events on no matter; another matter's event is refused (403) | `apps/calendar/access.py` |
| A contact's matters, and assigning a contact to a matter | Only their matters are listed; assigning to or removing from another matter is refused (403) | `apps/contacts/access.py` |
| Time, expense and flat-fee entries | Entries on their matters | `apps/activity/access.py` |
| Notes | Notes on their matters, and library notes | `apps/notes/access.py` |

Not checked against matter membership (sign-in only):

| Area | Paths | Location |
|---|---|---|
| Matter switcher partial | `/matters/<id>/switcher` (matter name) | `apps/matters/views.py:575` |
| Contacts (the contact's own record; contacts are firm-wide) | `/contacts/…` | `apps/contacts/` |
| Contacts in in-app search results | `/search/…` | `apps/search/views.py` |
| Invoicing, trust and reports (for a user who holds those flags) | `/invoicing/…`, `/reports/…` | |

### Financial (`perm_financial`)

| Gate | Location | Blocked |
|---|---|---|
| Middleware: `/invoicing/…`, `/matters/<id>/rates…`, `/matters/<id>/ledger…` | `apps/accounts/middleware.py:31`, `:40` | 403 |
| Matter Ledger tab, list and PDF (`/matters/<id>/ledger/…`), checked again in the view | `apps/matters/ledger/views.py:17` | 403 |
| Matter tab switch to `ledger` or `rates` (`/matters/<id>/tab/<tab>/`) | `apps/matters/views.py:381`, `:398` | 403 |
| Balance due and trust figures on the matter Overview | `apps/matters/views.py:199` | Figures omitted |
| Bulk "change matter" and "comp" on time entries | `apps/activity/time/views.py:579`, `:636` | 403 |
| Bulk "change matter" and "comp" on expenses | `apps/activity/expenses/views.py:362`, `:421` | 403 |
| Bulk "change matter" and "comp" on flat fees | `apps/activity/flat_fees/views.py:310`, `:343` | 403 |
| Bulk comp on an invoice's time entries (already under `/invoicing/`) | `apps/invoicing/invoices/views.py:115`, `:328` | 403 |
| Token API: `ledger` and `trust` sections, invoice read | `apps/case/api.py:68`, `:557`, `:672` | 403, JSON error |

Not checked against `perm_financial`:

| Area | Paths | Location |
|---|---|---|
| Time, expense and flat-fee lists (the Rate and Fee columns of the time list, the Amount column of the other two) | `/activity/…` | `templates/activity/time/list.html:220`; `apps/activity/` |
| Token API sections `rates`, `activity`, `settlement` | `/case/api/matter/<id>/<section>/` | `apps/case/api.py:65` (`FINANCIAL_SECTIONS`) |

### Intakes (`perm_intakes`)

| Gate | Location | Blocked |
|---|---|---|
| Middleware: `/intakes/…`, `/settings/intake-emails/…` | `apps/accounts/middleware.py:31` | 403 |
| Intakes in token search (`/search/api/`) | `apps/search/api.py:85` | Intakes omitted |
| Intakes in in-app search results, and the search window's Intakes tab | `apps/search/views.py:80`, `:121` | Intakes omitted, tab not shown |

### Reports (`perm_reports`)

| Gate | Location | Blocked |
|---|---|---|
| Middleware: `/reports/…` | `apps/accounts/middleware.py:31` | 403 |
| Firm-wide "Unbilled Time" breakdown on the dashboard (by user and by matter) | `apps/dash/views.py:79` | Shows the user's own figures instead |

### Research (`perm_research`)

| Gate | Location | Blocked |
|---|---|---|
| Middleware: `/case/research/…`, `/case/<matter_id>/research/…`, `/case/<matter_id>/tab/research/` | `apps/accounts/middleware.py:40` | 403 |

No view checks this flag; the middleware is the gate.

### Admin role

| Gate | Location | Blocked |
|---|---|---|
| Middleware: `/admin/…` and the six `/settings/…` paths in `ADMIN_ONLY_PATHS` | `apps/accounts/middleware.py:50`, `:64` | 403 |
| Toggle a permission, open or change matter assignments, checked again in the view | `apps/settings/users/views.py:129`, `:154`, `:176` | 403 |
| Delete a matter | `apps/matters/views.py:589` | 403 |
| Delete a voided invoice | `apps/invoicing/invoices/views.py:643` | 403 |
| Add, edit, delete a time-entry abbreviation code | `apps/activity/time/views.py:721`, `:743`, `:772` | 403 with a message |
| Connect or disconnect Google Calendar, Contacts or Drive (Gmail is open to every user) | `apps/settings/integrations/views.py:102` | 403 |
| "Collections" section on the dashboard | `apps/dash/views.py:127` | Section omitted |
| Everyone's tasks, events and time entries in the AI agenda context | `apps/dash/agenda.py:130`, `:147`, `:162` | Own and unassigned items only |

User-management routes under `/settings/users/`
(`apps/settings/users/views.py`):

| Route | Methods | Other checks |
|---|---|---|
| Change role (`change_role`, `:66`) | POST only (405 otherwise) | 400 unless the role is `ADMIN` or `USER` |
| Switch status (`switch_status`, `:76`) | POST only | |
| Toggle a permission (`toggle_permission`, `:128`) | POST only | 400 unless the name is one of the five flags |
| Toggle a matter assignment (`toggle_matter_assignment`, `:174`) | POST only | |

None of these routes, nor the user edit form, checks whether the change
removes the last active admin or the acting user's own Admin role.

## Navigation gates

These template conditions decide what a user is shown. The last column says
whether the server also refuses the request.

| Element | Shown to | Template | Server-side check |
|---|---|---|---|
| Sidebar: Invoicing | Admin or `perm_financial` | `templates/sidebar.html:71` | Yes (middleware) |
| Sidebar: Intakes | Admin or `perm_intakes` | `templates/sidebar.html:81` | Yes (middleware) |
| Sidebar: Reports | Admin or `perm_reports` | `templates/sidebar.html:91` | Yes (middleware) |
| Case navigation: Research tab | Admin or `perm_research` | `templates/case/includes/case-nav.html:59` | Yes (middleware) |
| Matter navigation: Rates tab | Admin or `perm_financial` | `templates/matters/includes/detail-nav.html:17` | Yes (middleware, and the tab switch in the view) |
| Matter navigation: Ledger tab | Admin or `perm_financial` | `templates/matters/includes/detail-nav.html:55` | Yes (middleware and view) |
| Matter form: Delete button | Admin | `templates/matters/form.html:28` | Yes (view) |
| Activity lists: selection column and bulk actions | Admin or `perm_financial` | `templates/activity/time/list.html:191`, `expenses/list.html:183`, `flat-fees/list.html:146` | Bulk matter and comp only |
| A matter's Time list: the Matter and Comp bulk menus (the selection column and the Category menu are for everyone) | Admin or `perm_financial` | `templates/matters/activity/list.html`; `apps/matters/activity/views.py:413`, `:473` | Yes |
| Time codes: add and edit buttons | Admin | `templates/activity/time/codes/list.html:20`, `results.html:11` | Yes (view) |
| Invoice detail: delete a voided invoice | Admin | `templates/invoicing/invoices/detail/detail.html:46` | Yes (view) |
| Settings menu: Firm | Admin | `templates/settings/main.html:14` | Yes (middleware) |
| Settings menu: Users, Permissions, Contacts, Practice Areas, Tasks | Admin | `templates/settings/main.html:25` | Yes (middleware) |
| Settings menu: Intake Forms, Intake Emails | Admin or `perm_intakes` | `templates/settings/main.html:52` | Yes (middleware) |
| Settings menu: Checklists | Admin or `perm_financial` | `templates/settings/main.html:65` | No (`/checklists/…`) |
| Integrations page: Google account section | Admin | `templates/settings/integrations/index.html:4` | Yes (view) |

## Routes that need no sign-in

"App limit" is the application's own rate limit from
[`utils/ratelimit.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/utils/ratelimit.py):
a count per client IP address, kept separately in each web worker process.
The address is the last entry of the `X-Forwarded-For` header, the one
nginx appends. The nginx limits in the
[security checklist](../admin/security.md#tls-and-nginx) apply on top.

| Route | Methods | Purpose | Protected by | App limit |
|---|---|---|---|---|
| `/accounts/login/` | GET, POST | Username and password step | Password | None |
| `/accounts/login/verify/` | GET, POST | Emailed code step | Session from the password step, plus the code. Five wrong codes delete the code. | None |
| `/accounts/logout/` | GET, POST | Sign out | Nothing | None |
| `/accounts/password_reset/`, `/accounts/password_reset/done/` | GET, POST | Request a password-reset email | Nothing | None |
| `/accounts/reset/<uidb64>/<token>/`, `/accounts/reset/done/` | GET, POST | Set a new password | Django's signed reset token (three days) | None |
| `/admin/login/` | Any | Redirects to `/accounts/login/`. A `next` value is kept only when it stays on the same host; otherwise the admin index is used. | Nothing. It has no form and signs nobody in. | None |
| `/health/live/` | GET, HEAD | Returns `{"status": "ok"}` | Nothing | None |
| `/health/ready/` | GET, HEAD | Runs `SELECT 1`; 200 or 503 | Nothing | None |
| `/health/worker/` | GET, HEAD | 200 when no repeating schedule is more than five minutes overdue; 503 when one is, when no schedules are installed, or when the database cannot be read | Nothing | None |
| `/pay/<token>/` | GET | Invoice payment page | Signed token (invoice UUID, `INVOICE_PAY_LINK_MAX_AGE`) | None |
| `/pay/<token>/invoice.pdf` | GET | Invoice PDF | Same token; refused for a voided invoice | 30 per 5 min |
| `/pay/<token>/charge/` | POST | Charge the invoice balance | Same token; CSRF-exempt | 20 per 5 min |
| `/pay/balance/<token>/` | GET | Matter balance or trust deposit payment page | Signed token (payment request UUID, `INVOICE_PAY_LINK_MAX_AGE`); refused once the request is canceled | None |
| `/pay/balance/<token>/statement.pdf` | GET | Matter statement PDF | Same token; not for trust requests | 30 per 5 min (shared with the other PDFs) |
| `/pay/balance/<token>/invoice/<id>.pdf` | GET | PDF of an invoice on the same matter | Same token; invoice must belong to the request's matter | 30 per 5 min (shared) |
| `/pay/balance/<token>/charge/` | POST | Charge the requested amount | Same token; CSRF-exempt | 20 per 5 min (shared with the invoice charge) |
| `/webhooks/<processor>/` | POST | Payment processor notifications | Per processor: see [Payment webhooks](../admin/security.md#payment-webhooks). Always answers 200. CSRF-exempt. | 240 per minute per processor name |
| `/form/<token>/` | GET | Client intake form | Signed token (submission UUID, `INTAKE_FORM_LINK_MAX_AGE`); refused once canceled | 60 per 5 min |
| `/form/<token>/save/` | POST | Autosave answers | Same token; CSRF token from the page | 120 per 5 min |
| `/form/<token>/submit/` | POST | Submit the form | Same token; CSRF token from the page | 20 per 5 min |
| `/api/receive-inquiry/` | POST | Create an intake, or add a note to a matching one | `X-Seam-Key` header equal to `KOSMOS_SEAM_KEY`, compared in constant time. While that variable is blank, every request gets 403. CSRF-exempt. | None |
| `/api/receive-intake/` | POST | Create an intake, add a note, or overwrite a note on an intake | Same as above | None |
| `/api/intakes/search/` | GET | Returns up to 20 intakes: name, phone, email, status, date, practice area | Same as above | None |
| `/api/inbound-email/` | POST | Mailgun inbound route | HMAC-SHA256 signature with `MAILGUN_WEBHOOK_SIGNING_KEY`, five-minute window. While that variable is blank, every post gets 403. Then: recipient must match `INTAKE_INBOUND_RECIPIENT` and the From address must be an active user's email. CSRF-exempt. | 60 per minute |
| `/media/company/<path>` | GET | The firm logo | Nothing. Routed only when `STORAGE_BACKEND=local`. | None |
| `/static/<path>` | GET | CSS, JavaScript, images | Nothing. Served by nginx. | None |

When the payment processor cannot serve a `/pay/…` page as configured, the
page answers 503 with "Online payment is not available right now. Please
contact us."

The signed tokens are made with `SECRET_KEY`
([`utils/signing.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/utils/signing.py)),
with a different salt for each of the three kinds, so one kind cannot be
used in place of another.

## Token-authenticated APIs

These take no session. Each request carries the user's token in the
`X-Kosmos-Token` header. All are CSRF-exempt and have no application rate
limit.

| Fact | Value |
|---|---|
| Token model | `CompanionToken`, one per user (`apps/drafts/models.py:89`) |
| Format | `secrets.token_urlsafe(32)`, stored as-is in the database |
| Expiry | None |
| Issued | By the user: Settings → Claude Desktop, or the first time they open the LibreOffice companion setup |
| Rotated or revoked | By the user only, in Settings → Claude Desktop |
| Missing, unknown, or user inactive | 401 with a JSON error (`apps/drafts/api_auth.py:38`, `apps/drafts/companion.py:59`) |

| URL prefix | Decorator | Methods | Scope |
|---|---|---|---|
| `/notes/api/matters/` | `kosmos_api_auth` | GET | Open matters the user can access |
| `/notes/api/notes/`, `/notes/api/search/` | `kosmos_api_auth` | GET | Library notes (shared by everyone) plus notes of open matters the user can access |
| `/notes/api/notes/<id>/` | `kosmos_api_auth` | GET | Any library note; a matter note only with matter access; otherwise 404 |
| `/notes/api/notes/<id>/write/` | `kosmos_api_auth` | POST | Same access, and the note's AI-write grant must be current (`Note.ai_write_until`); otherwise 403 |
| `/case/api/matter/<id>/<section>/` | `kosmos_api_auth` | GET | Open matter the user can access; otherwise 404 |
| `/case/api/matter/<id>/facts/`, `/case/api/matter/<id>/witnesses/` | `kosmos_api_auth` | GET, POST | Same; POST creates one row |
| `/case/api/matter/<id>/emails/<thread_id>/` | `kosmos_api_auth` | GET | Same |
| `/case/api/matter/<id>/conversations/<id>/` | `kosmos_api_auth` | GET | Same; conversations marked never to be AI context are excluded |
| `/case/api/matter/<id>/search/` | `kosmos_api_auth` | POST | Same |
| `/case/api/documents/<id>/` | `kosmos_api_auth` | GET | Document on an open matter the user can access; otherwise 404 |
| `/case/api/invoices/<id>/` | `kosmos_api_auth` | GET | Invoice on an open matter the user can access (404), and financial access (403) |
| `/case/api/tasks/` | `kosmos_api_auth` | POST | Creates a task for the token's user; an optional matter must be open and accessible |
| `/search/api/` | `kosmos_api_auth` | GET | Matters, proceedings and matter notes limited to accessible matters of any status; contacts unrestricted; intakes only with `perm_intakes` |
| `/case/drafts/companion/api/…` | `companion_auth` | GET, POST | Draft links whose conversation belongs to the token's user; otherwise 404 |

Sections served by `/case/api/matter/<id>/<section>/` and what each
requires beyond matter access:

| Section | Extra requirement |
|---|---|
| `overview`, `contacts`, `rates`, `activity`, `events`, `tasks`, `proceedings`, `settlement`, `documents`, `highlights`, `timeline`, `witnesses`, `emails`, `conversations` | None |
| `ledger`, `trust` | Admin or `perm_financial`; otherwise 403 `{"error": "Your Kosmos account does not have financial access."}` |

`perm_reports` and `perm_research` are not consulted by any token API.
