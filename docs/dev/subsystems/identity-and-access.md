# Identity and access

Who a user is, how they sign in, and what they may reach. The user model
and the sign-in flow live in `apps/accounts/`; the path and matter checks
run in middleware from the same app; each application that lists records
by matter narrows them through its own `access.py`; and the per-user API
token that the LibreOffice companion and the MCP server present lives in
`apps/drafts/`. The matrix of what each flag opens is generated into
[Permissions matrix](../../reference/permissions.md); this page explains
the machinery behind it and does not repeat the gates.

## Where the code is

| Module | Holds |
|---|---|
| `apps/accounts/models.py` | `CustomUser`, `EmailVerificationCode`, `Authenticator`, `SignInThrottle` |
| `apps/accounts/backends.py` | `EmailBackend`: sign-in by email address |
| `apps/accounts/views.py` | The two-step sign-in (`LoginView`, then `VerifyCodeView` or `AuthenticatorCodeView`) |
| `apps/accounts/totp.py` | Authenticator secrets: encryption, QR code, code checks |
| `apps/accounts/utils.py` | Code generation and the email that carries it |
| `apps/accounts/middleware.py` | `HtmxLoginRedirectMiddleware`, `PermissionMiddleware`, `AuthenticatorRequiredMiddleware` |
| `apps/accounts/access.py` | `matter_access_required`, `filter_matters_for_user`, `MATTER_LOOKUPS`, `user_may_use_route` |
| `apps/accounts/managers.py` | `CustomUserManager`: `createsuperuser` makes an `ADMIN` |
| `apps/dash/middleware.py` | `DailyDashCheckMiddleware`, the once-a-day Dash redirect |
| `apps/<app>/access.py` | Per-application queryset narrowing and direct-hit refusals (list below) |
| `apps/settings/users/` | The Users page: create, edit, role, status, flags, matter assignments, authenticator reset |
| `apps/settings/security/` | Settings > Security: the user's own authenticator app |
| `apps/settings/permissions/` | The read-only permissions matrix page |
| `apps/settings/claude/views.py` | Issue, rotate and revoke the API token |
| `apps/drafts/models.py` | `CompanionToken` |
| `apps/drafts/api_auth.py`, `apps/drafts/companion.py` | `kosmos_api_auth` and `companion_auth`, the token decorators |
| `templates/registration/` | `login.html`, `verify_code.html`, `verify_authenticator.html` |

## Data model

**`CustomUser`** extends Django's `AbstractUser` and is the
`AUTH_USER_MODEL`. Beyond Django's own fields it carries:

- `role`: `ADMIN` or `USER` (`ROLE_OPTIONS`). `is_admin` is a property on
  the role. Django's `is_staff` and `is_superuser` are separate and
  nothing consults them (there is no Django admin). `createsuperuser`
  sets all three.
- `email` is the sign-in name. A `UniqueConstraint` on `Lower("email")`,
  conditioned on the address not being blank, keeps each address to one
  user; `UniqueEmailMixin` (`apps/accounts/forms.py`) gives every form
  that edits it the same rule with a readable message. `username` is a
  display name.
- The five permission flags, listed in `CustomUser.PERM_FIELDS`:
  `perm_all_matters`, `perm_financial`, `perm_intakes`, `perm_reports`,
  `perm_research`. All default to on except `perm_reports`. The Users page
  toggles them one at a time (`toggle_permission` validates the name
  against its own `VALID_PERMS` list, which must match `PERM_FIELDS`).
- `user_rate`: the default hourly rate. A time entry takes the matter's
  `Rate` row for that user when one exists and this otherwise
  (`calculate_rate_for_matter()` in `apps/activity/time/views.py`,
  `build_timekeepers()` in `apps/matters/timekeepers.py`).
- `initials`, `is_attorney`, `title`: display and AI-context fields.
  `title_display` falls back to "Attorney" or "Staff" from the flag.
- `last_dash_check`: the date of the user's last visit to the Dash, kept
  on the user so the daily check-in holds across devices.
- `digest_enabled`, `digest_include_weekends`, `nav_layout`,
  `task_user_chips`: per-user preferences owned by other subsystems.
- `assigned_matters`: the reverse of `Matter.members`, the membership that
  `perm_all_matters` off is measured against.
- `history = HistoricalRecords()`: every change to a user row is kept by
  django-simple-history, password hash included. The operator guide's
  [Change history](../../admin/security.md#change-history) says what that
  means for backups and pruning.

**`EmailVerificationCode`** is one row per pending sign-in: `user`, the
six-digit `code` stored in clear, `created_at`, and `attempts`. The
`attempts` counter is on the code and not in the session on purpose, so
opening more browser sessions does not multiply the guesses. `is_expired()`
measures five minutes with `total_seconds()`; the comment there records
why `.seconds` was wrong (it wraps every 24 hours).

**`Authenticator`** is one row per user with an authenticator app:
`user` (one-to-one), the TOTP `secret` in clear, and `last_counter`, the
30-second step of the last code accepted, so a code is good once. The
secret is deliberately not encrypted (the module docstring of
`apps/accounts/totp.py` says why: a key on the same server protects
little, and tying enrolments to `SECRET_KEY` un-enrols everyone when it
rotates; cpl made the same choice). Its own row, rather than fields on
`CustomUser`, keeps it out of `HistoricalCustomUser`.

**`SignInThrottle`** is one row per email address that has failed a
sign-in, as typed and lowercased, whether or not it belongs to a user:
`failures` and `last_failure_at`. `cooldown_for(failures)` is zero below
`FREE_FAILURES` (5), then `COOLDOWN_BASE` (30 s) doubling to
`COOLDOWN_CAP` (15 min). `record_failure()` forgets failures older than
`FAILURE_MEMORY` (an hour) before counting, and drops rows untouched for
a day. It is a table, not a cache entry, so the count is the same in
every worker process.

**`CompanionToken`** is a `OneToOneField` to the user with a `key` from
`secrets.token_urlsafe(32)` (`unique=True`, no expiry). `for_user()` is a
`get_or_create`, so a user has at most one token and the LibreOffice
companion and Claude Desktop share it.

Nothing about permissions is enforced in the database. The flags are
booleans, `role` is a `CharField` with choices, and matter membership is
an ordinary many-to-many table.

## How it works

### Sign-in

Every view carries `@login_required`; there is no global sign-in
middleware. The sign-in itself is two steps in `apps/accounts/views.py`,
mounted at `accounts/login/` and `accounts/login/verify/` ahead of
`django.contrib.auth.urls`:

1. `LoginView` takes `EmailLoginForm` (email and password). Before the
   password is looked at, `SignInThrottle.locked_until(email)` is
   checked: in a cooldown, the page answers with the wait and nothing
   else runs. Otherwise `authenticate()` goes through `EmailBackend`, the
   only backend in `AUTHENTICATION_BACKENDS`: it finds the user by
   `email__iexact`, and when there is none still runs a hash so the
   timing is the same. A failure calls `record_failure()`. On success the
   view stores `pending_user_id` and `pending_email` in the session (the
   `next` parameter too, when `_safe_next_url()` accepts it as same-host)
   and then branches: a user with an `authenticator_for()` row is sent to
   the authenticator page; anyone else gets a fresh `EmailVerificationCode`
   (any earlier one deleted), sent with `send_verification_email()`
   through `send_mail`, and the verify page.
2. `VerifyCodeView` needs `pending_user_id` in the session, otherwise it
   sends the user back to step 1. It compares the submitted code with
   `hmac.compare_digest()`. A wrong code increments `attempts` with an
   `F()` expression; at `MAX_CODE_ATTEMPTS` (5) the code is deleted and
   the session cleared, so the user must pass the password step again. An
   expired code is deleted the same way. On success the code is deleted
   and `_finish_login()` runs.
3. `AuthenticatorCodeView` is the alternative second step. It refuses
   during a cooldown, and a wrong code is a `record_failure()` like a
   wrong password, so the app gets the same budget of guesses. The code
   is checked by `totp.verify()`: the step that matches, within one step
   of drift either side, must be later than the row's `last_counter`,
   which it then becomes in one guarded `UPDATE … WHERE last_counter <
   step`, so two requests racing with the same code cannot both win.
   There is no route from here to the emailed
   code; an enrolled user who reaches `VerifyCodeView` finds no code row
   and is sent back to step 1.

`_finish_login()` clears the throttle row for the address, forgets the
pending keys, calls `login()` and sends the user to `login_next_url` or
`LOGIN_REDIRECT_URL` (`tasks:index`). The throttle is cleared only here,
not after the password step, so a known password does not buy unlimited
code guesses.

`AuthenticatorRequiredMiddleware` enforces `Firm.require_authenticator`:
a signed-in user without an `Authenticator` row may reach only
`/settings/security/`, `/accounts/` (sign-out), `/static/` and `/media/`;
any other path is a redirect there (`HX-Redirect` for an HTMX request).
It runs after `PermissionMiddleware` and costs one `Firm` read per
request.

Enrolment is in `apps/settings/security/views.py`: `authenticator_setup`
makes a secret with `pyotp.random_base32()`, keeps it in the session
under `authenticator_setup_secret` and renders the QR code (`segno`,
inline SVG, black on white whatever the theme) and the key in groups of
four; `authenticator_confirm` checks a code against that secret and only
then writes the row through `totp.enrol()`, recording the confirming
code's step as spent. `authenticator_disable` takes a current code and
is a 403 while the firm requires the app. An administrator's
`reset_authenticator` view on the Users page, and the
`reset_authenticator` management command, delete the row.

There is no Django admin: `django.contrib.admin` is not installed and no
app has an `admin.py`. One consequence for the app registry is under
Things that bite.

Sessions are database-backed, last `SESSION_COOKIE_AGE` (56 days) and are
renewed on every request (`SESSION_SAVE_EVERY_REQUEST`). On `ENV=dev` the
session engine is file-based under `.dev-sessions/`, because the nightly
database reload would otherwise sign everyone out. Deactivating a user
(`is_active` off) ends their sessions through Django's own
`ModelBackend.user_can_authenticate()`; nothing in the application has to
do it.

Sessions, the throttle and the authenticator rows are the only sign-in
state. Nothing is cached, so prod's several worker processes agree.

`HtmxLoginRedirectMiddleware` turns the `302` a logged-out HTMX request
would get into a `200` with an `HX-Redirect` header, so an expired session
sends the whole page to the sign-in form instead of swapping the form into
a fragment.

### The daily Dash check

`DailyDashCheckMiddleware` (`apps/dash/middleware.py`) redirects the first
full-page request of each local day to `dash:index`, and the Dash request
itself writes today's date to `last_dash_check`. HTMX and XHR requests,
`/accounts/`, `/static/`, `/media/` and the debug toolbar are exempt, so a
partial update is never answered with a redirect.

### Path rules

`PermissionMiddleware.__call__` runs before URL resolution. Its first
check applies to every request: a path matching `AI_PATTERN` while no AI
provider is configured, or `CASELAW_PATTERN` while there is no
CourtListener token, gets `404` (the feature does not exist on this
server; see [AI is optional](ai/context.md#ai-is-optional)). The rest
runs for signed-in non-admins only and answers `403` with an empty body.
It checks, in order: `ADMIN_ONLY_PATHS` (the settings pages that change the
firm); `PERMISSION_PATHS`, a list of `(prefix, flag)` pairs; then
`PERMISSION_PATTERNS`, compiled regexes for pages whose path begins with a
matter id (`/matters/<id>/rates`, `/matters/<id>/ledger`, and the Research
tab's routes, saved cases and the case viewer's cluster pages included).
The comment above `PERMISSION_PATTERNS` states the rule: hiding a tab in
the navigation is not a gate, the URL has to refuse too.

### Matter membership

Three functions in `apps/accounts/access.py` carry the whole rule, and
every other check calls one of them:

- `CustomUser.has_matter_access(matter)`: true for an admin, for
  `perm_all_matters`, or for a member.
- `filter_matters_for_user(queryset, user)`: the queryset unchanged for the
  first two, `filter(members=user)` otherwise.
- `matter_access_required`: a view decorator that reads `id` or
  `matter_id` from the URL keywords and raises `PermissionDenied`.

Views under `/matters/<id>/…` use the decorator. Routes under `/case/`
cannot, because most of them name a document, a fact or a conversation by
its own id with no matter in the URL. For those,
`PermissionMiddleware.process_view` runs after resolution (the only
`process_view` in the stack) and calls
`user_may_use_route(user, view_kwargs)`. That function
maps each URL keyword in `MATTER_LOOKUPS` to the model that owns it and
the field path to its matter (`"message_id"` leads through
`conversation__matter_id`, `"highlight_id"` through either a document or
a saved case), collects every matter the route touches, and refuses unless
the user is a member of all of them. `OBJECT_TYPE_KEYS` covers the pickers
that pass `(object_type, object_id)` instead. Users who see every matter
are never looked up. An id that matches nothing, or a row with no matter
(a library note, an intake chat), contributes nothing and is left to the
view. This replaced, in October 2026, a design where those routes checked
only for a session: see the commit "fix(access): enforce matter membership
and permission flags at the URL".

Only `/case/` is in `MATTER_SCOPED_PREFIXES`. `/matters/` and `/notes/`
carry their own checks, as do ids that arrive in a query string or a POST
body anywhere: the middleware never sees those.

### The per-application access modules

Outside `/matters/<id>/` and `/case/`, each application that lists records
by matter has an `access.py` with the same two shapes:

- a **queryset narrower** for lists and exports, built on
  `filter_matters_for_user()` or `user.assigned_matters`: `tasks_for_user`,
  `events_for_user`, `entries_for_user`, `relationships_for_user`,
  `documents_for_user`, `visible_notes_q`;
- a **by-id fetch** for a direct hit that does `get_object_or_404` and then
  raises on the matter: `task_for_user`, `event_for_user`, `entry_for_user`,
  `relationship_for_user`, `conversation_for_user`, `note_for_user`.

The modules are `apps/activity/access.py`, `apps/tasks/access.py`,
`apps/calendar/access.py`, `apps/contacts/access.py`,
`apps/intakes/access.py`, `apps/notes/access.py`, `apps/case/ai/access.py`,
`apps/case/facts/access.py` and `apps/case/documents/access.py`. Each
module's docstring states its rule; three are worth knowing before you
add a view:

- A task, event or note on **no matter** is the firm's, and every signed-in
  user may reach it. The narrowers express this as
  `Q(matter__isnull=True) | Q(matter__in=…)`.
- The refusal is `PermissionDenied` (403) everywhere except
  `apps/notes/access.py`, which raises `Http404` so a refusal does not
  confirm the note exists; `matter_conversation_for_user` in
  `apps/case/ai/access.py` folds the matter into the lookup for the same
  reason.
- Each module also owns the **matter choices** its forms offer
  (`matters_for_task_form`, `matters_for_events`, `matters_for_entry_form`,
  `open_matters_for_user`, `matters_for_note_form`). They differ in which
  statuses they list, and each takes `include_id` to keep the record's
  current matter in the list whatever its status;
  `apps/case/documents/access.py` explains what goes wrong without it (the
  browser picks the first option and saving moves the record).

`apps/case/facts/access.py` and `apps/case/documents/access.py` exist for
what the middleware cannot see: a source, label or destination matter
posted in the body must belong to the same matter as the thing it is
attached to.

### Tokens

`kosmos_api_auth` (`apps/drafts/api_auth.py`) and `companion_auth`
(`apps/drafts/companion.py`) read `X-Kosmos-Token`, look up the
`CompanionToken` with `select_related("user")`, and answer `401` when the
key is unknown or `token.user.is_active` is false. Deactivating a user
therefore revokes the token without touching it. The two decorators are
kept separate so the API's 401 body can tell the user where to get a new
token without changing the `.oxt` client's contract. Both set a request
attribute (`api_user`, `companion_user`) and are `csrf_exempt`; the view
then applies the same `has_matter_access` and flag checks a session view
would. Which routes use which decorator, and what each exposes, is in
[Token-authenticated APIs](../../reference/permissions.md#token-authenticated-apis);
the APIs themselves are in [MCP server and JSON APIs](mcp.md).

The Settings → Claude Desktop page issues the token on first visit through
`CompanionToken.for_user()`. `claude_rotate` deletes and recreates the row;
`claude_revoke` deletes it. Rotating re-keys the LibreOffice companion as
well, since it is the same row.

### User administration

`apps/settings/users/views.py` is admin-only at the middleware
(`/settings/users/` is in `ADMIN_ONLY_PATHS`), and `toggle_permission`,
`matter_assignments` and `toggle_matter_assignment` check `is_admin` again
in the view. State changes are `POST`-only since October 2026, when they
were found to run on `GET` from a link.

`_is_last_admin(user)` guards the firm against locking itself out: a user
who is the only active administrator cannot be demoted (`change_role`),
deactivated (`switch_status`) or edited into either state (`edit_user`).
The refusal is a `204` carrying a toast, not an error page, because the
callers are HTMX. The docstring gives the reason: settings are open to
administrators alone, so a firm with none is locked out until someone uses
the server's command line.

Users are deactivated, never deleted, from the application; prefer
`is_active` to deleting a user row from a shell.

## Access

Everything on this page is the access layer; the matrix of who passes
what is [Permissions matrix](../../reference/permissions.md). Two facts
belong here because they are easy to get wrong when adding a feature:

- A new flag needs a line in `PERM_FIELDS`, in `VALID_PERMS` in
  `apps/settings/users/views.py`, in `PERM_COLUMNS` in
  `apps/settings/permissions/views.py` (the matrix page), and a migration. The
  permissions reference is generated from the code; do not edit it by
  hand.
- The Reports flag starts off. Migration
  `apps/accounts/migrations/0017_reports_permission_off_by_default.py`
  flipped the default and turned it off for every non-admin, with the
  reason in its docstring: until then every report also required
  `is_staff`, so the flag had never gated anything, and switching the
  reports to the flag alone with it defaulting to on would have shown the
  firm's revenue to everyone.

## Things that bite

- **A `/case/` route that gains a new kind of id is unprotected until
  `MATTER_LOOKUPS` has a line for it.** The comment above the table says
  so. The lookup only knows the keywords listed there; an unknown keyword
  contributes no matter, and the route passes.
- **Membership is checked from the URL only.** An id in a query string
  or a POST body bypasses `process_view`. Use the application's
  `access.py` fetchers (`matter_conversation_for_user`, `source_for_fact`,
  `target_matter_for_user`) for those.
- **Three lists must agree.** `PERM_FIELDS`, `VALID_PERMS` and
  `PERM_COLUMNS` each name the flags. Miss one and the toggle returns
  `400` or the matrix page omits the flag.
- **`is_staff` is not the Admin role.** The application's checks read
  only `role`; `is_staff` and `is_superuser` are set by `createsuperuser`
  and read by nothing.
- **Sub-package models must be imported from the app's `models.py`.**
  `apps/invoicing/models.py`, and the foot of `apps/activity/models.py`
  and `apps/matters/models.py`, import the models that live in
  sub-packages (`invoicing/payments/models.py`, `activity/time/models.py`,
  `matters/rates/models.py` and the rest). Until the admin was removed,
  the `admin.py` files imported them at start-up as a side effect; without
  those imports the registry lacks them until a URL import happens to load
  them, and anything earlier (a `shell` one-liner, the test database's
  serialisation) fails with "Related model 'invoicing.payment' cannot be
  resolved". A new sub-package model needs a line there.
- **Tests sign in with `force_login`.** `client.login(username=...)`
  reaches `EmailBackend`, which reads the value as an email address, so a
  username there finds nobody.
- **The code is stored in clear and counted on the row.** Tests that
  assert on guesses must count `EmailVerificationCode.attempts`, not
  session state; and a second `LoginView` POST deletes the first code, so
  a user who re-submits the password form invalidates the code already in
  their inbox.
- **`SESSION_SAVE_EVERY_REQUEST` writes a session row on every hit**,
  including HTMX polls. The 56-day lifetime is fixed in
  `config/settings.py`, not in the environment.
- **The daily Dash redirect fires on any full-page request**, including
  one from a bookmark to a deep link, and the `next` location is not kept.
  A new full-page route that must not be interrupted needs an entry in
  `DailyDashCheckMiddleware.EXEMPT_PATHS`.

## Related

- [Users and permissions](../../admin/users.md) (operator guide): creating
  the first administrator, roles, assigning matters, deactivating.
- [Security checklist](../../admin/security.md): the sign-in hardening
  points and the nginx rate limit on the login path.
- [Permissions matrix](../../reference/permissions.md).
- [Settings](../../guide/settings.md) (user guide): the Users and
  Permissions screens.
- [Matters](matters.md): `Matter.members` and what membership covers.
- [MCP server and JSON APIs](mcp.md): the token-authenticated surface.
- [Architecture](../architecture.md): the middleware stack in request
  order.
