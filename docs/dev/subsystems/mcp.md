# MCP server and JSON APIs

Claude reaches Kosmos through a remote MCP server that Kosmos itself
serves at `/mcp`, behind an OAuth 2.1 authorization server that is also
Kosmos's own (`apps/mcp`). The tools call the same service functions as
the token-authenticated JSON APIs in `apps/ai/api.py` (under `case/api/`)
and `apps/search/api.py`. User-facing setup is in the operator guide:
[Claude](../../admin/integrations/claude-desktop.md).

Access is per user. An MCP request carries a bearer token that a user
issued by signing in to Kosmos and clicking Allow; the tools run as that
user, so Claude sees exactly what the user can see, disconnecting under
Settings → Claude ends the tokens, and deactivating the user kills them
all. The JSON APIs keep their separate `X-Kosmos-Token` key
(`ApiToken`), shared with the LibreOffice companion; the MCP server does
not accept it.

## Where the code is

| Module | Holds |
|---|---|
| `apps/mcp/server.py` | The MCP endpoint: bearer check, the JSON-RPC dispatch (`initialize`, `ping`, `tools/list`, `tools/call`), the 401 that starts sign-in |
| `apps/mcp/tools.py` | The fifteen tools: descriptions, JSON schemas, and the text each makes of a service function's result |
| `apps/mcp/oauth.py` | The authorization server: metadata documents, registration, the consent screen, the token and revocation endpoints, redirect-URI and PKCE checks |
| `apps/mcp/models.py` | `McpClient`, `McpAuthorizationCode`, `McpConnection`, `McpToken` |
| `apps/mcp/urls.py` | The well-known documents at the root, `/mcp`, `/mcp/oauth/*` |
| `templates/mcp/` | The consent screen and the refusal page, on the sign-in pages' shell |
| `apps/accounts/api_auth.py` | `kosmos_api_auth`, the `X-Kosmos-Token` decorator, and `ApiError`, what every service function raises |
| `apps/ai/api.py` | The service functions over a matter (`list_matters`, `read_section`, `read_document`, `read_email_thread`, `search_materials`, `read_conversation`, `read_invoice`, `create_fact`, `create_witness`, `create_task`, `create_time_entry`, `create_event`, `complete_task`, `create_contact`) and the JSON views over them |
| `apps/search/api.py` | `search_practice()` and its JSON view |
| `apps/settings/claude/views.py` | Settings → Claude: the connector address, the connections and Disconnect, the API token |
| `apps/ai/context.py` | The section formatters the matter API reuses |

## Data model

- **`McpClient`**: an OAuth client. Claude registers one dynamically
  (RFC 7591) when a connector is first set up, or identifies itself by
  a client ID metadata document, in which case `client_id` is the
  document's HTTPS URL and the row caches what it says
  (`is_metadata_document`). `redirect_uris` is what the consent screen
  will send the browser to; `secret_hash` is blank for a public client
  (Claude is one). A client has no access of its own.
- **`McpAuthorizationCode`**: the code the consent screen hands the
  browser, five minutes long, with the PKCE challenge and the redirect
  URI it was issued for. Deleted when redeemed.
- **`McpConnection`**: a user's standing authorization of a client,
  with `created_at` and `last_used_at`. This is what Settings → Claude
  lists and Disconnect deletes; its tokens go with it (`CASCADE`).
- **`McpToken`**: one access token (an hour) and the refresh token that
  replaces it (ninety days). Refreshing marks the row's refresh token
  used and creates the next row; the old access token lives out its
  hour, so a request in flight is not failed by a refresh.

Tokens, codes and secrets are stored as SHA-256 digests. They are
long random strings, so a digest is enough: a copy of the table cannot
be replayed, and a presented token is looked up by hashing it.

## How it works

### Discovery and sign-in

1. Claude posts to `/mcp` without a token and gets `401` with
   `WWW-Authenticate: Bearer resource_metadata="…/.well-known/oauth-protected-resource/mcp"`.
   The `401` is required: Claude ignores the header on any other status.
2. The protected resource metadata (RFC 9728) names the resource
   (`https://host/mcp`, which must equal the URL the user entered) and
   the authorization server (the site's base URL).
3. The authorization server metadata (RFC 8414) at
   `/.well-known/oauth-authorization-server` lists the endpoints and
   advertises `client_id_metadata_document_supported` with `none` among
   the token endpoint auth methods. With both present Claude identifies
   itself by its published metadata document and registers nothing;
   without them it falls back to dynamic registration at
   `/mcp/oauth/register`, which is also offered.
4. The browser is sent to `/mcp/oauth/authorize`. The view is
   `login_required`, so an anonymous user goes through the ordinary
   two-step sign-in and comes back (`next`). The consent screen names
   the client and the host it will return to, and Allow issues a code.
   `DailyDashCheckMiddleware` exempts `/mcp/`, or the once-a-day Dash
   redirect would swallow the flow.
5. Claude swaps the code at `/mcp/oauth/token` (form-encoded) with its
   PKCE verifier, and the resource it named is checked against this
   server's MCP URL (RFC 8707). A `McpConnection` and its first
   `McpToken` are made. Every later request carries the access token;
   a refresh rotates it.

Base addresses come from `PUBLIC_BASE_URL` when set, else the request.
There are no scopes: what a token reaches is what its user may reach.
Every redirect carries `iss` (RFC 9207).

### Redirect URIs

A registered redirect URI must be HTTPS, or plain HTTP to the loopback
address (Claude Code listens on one). At authorization time the URI must
match a registered one exactly, except that a loopback URI matches on
any port (RFC 8252 section 7.3): Claude Code picks a free port per
session. An unknown client or an unregistered redirect ends on a page
(`templates/mcp/error.html`), never on a redirect the request chose;
every other error goes back to the client as an `error` parameter.

### The endpoint

`POST /mcp` is streamable HTTP in its simplest form: one JSON-RPC message
in, one JSON object out (`application/json`), no event stream, no
session id. `GET` answers `405`, as the transport provides for a server
with no stream to offer. Notifications answer `202` with no body. The
protocol versions accepted are in `PROTOCOL_VERSIONS`; an
`MCP-Protocol-Version` header outside them is `400`. A browser-sent
`Origin` that is not this host is `403` (the transport's DNS-rebinding
guard).

Tool results are text. A refusal from a service function (`ApiError`)
comes back as a tool result with `isError: true` and the message
prefixed `Kosmos API error (<status>)`, so the model learns what was
wrong (a 404 it can retry with another id, a 403 it cannot). Arguments
that do not fit the schema are a JSON-RPC `-32602`.

### Tools

`find_matter`, `read_matter`, `search_matter`, `search_kosmos`,
`read_document`, `read_email_thread`, `read_conversation`,
`read_invoice`, `add_fact`, `add_witness`, `add_task`, `add_time_entry`,
`add_event`, `complete_task`, `add_contact`. Long reads
truncate at `READ_TRUNCATE_CHARS` (40k) with an explicit marker. All
intelligence lives in the service functions; `tools.py` only describes
and formats. `initialize` also returns `instructions` telling the model
to resolve a matter once and read the overview first. The contacts and
tasks sections are manifests with `[contact:ID]` and `[task:ID]`
handles (the contacts section also names the groups and roles
`add_contact` may use on the matter); they are formatted in `api.py`,
not shared with `apps/ai/context.py`.

## Access

Matters are the user's accessible open matters only, through
`filter_matters_for_user()`, and every denial of a matter, document,
thread or conversation is a 404 so it does not confirm existence. The
money sections (`FINANCIAL_SECTIONS`: rates, ledger, trust) and invoice
reads additionally need `has_financial_access()` (admin or
`perm_financial`), like the in-app Rates and Ledger tabs; that denial is
a 403, since the matter's existence is already known to the caller. The
activity section is open to every user who can see the matter, as the
Activity screens are. Intakes in the practice-wide search need
`perm_intakes`. Inactive users are refused at the token check, on both
the bearer and the `X-Kosmos-Token` paths. See the
[permissions reference](../../reference/permissions.md).

## Write access

Seven writes, none destructive. Six create a row; the seventh marks a
task complete, which the tasks page can undo. Nothing on the money side
(invoices, payments, trust) and nothing that sends mail is reachable.
The record is [Claude's writes stay
create-shaped](../../decisions/2026-10-30-claude-writes-stay-create-shaped.md).

- **Timeline facts and witnesses**: `create_fact` and `create_witness`
  reuse `_create_fact_from_entry()` and `_create_witness_from_entry()`
  (validation, matter scoping of cited ids, name dedup): exactly what
  the in-app chat's fenced blocks can do, no more.
- **Tasks**: `create_task` reuses `create_task_from_ai_entry()`,
  assigned to the acting user; the matter is authorized here, because
  the service resolves by name without an access check, and the task is
  re-pointed after creation in case a duplicate name resolved elsewhere.
  `complete_task` sets `STATUS_COMPLETE` through the model's `save()`,
  which stamps `date_completed`; the checklist guard
  (`can_complete_task()`) applies as on the tasks page, a task already
  complete is reported rather than failed, and a task on a matter the
  user cannot see is a 404.
- **Time entries**: `create_time_entry` takes a narrative, hours and an
  optional date and category (one of the matter's `ActivityCategory`
  rows, by name). The matter must be hourly, as the time form requires.
  The rate is `calculate_rate_for_matter()` for the acting user, never
  an argument; the entry is unbilled (`invoice` null, `entered` and
  `comp` false) and flagged `needs_approval`, which the Activity tab's
  Approve action clears (see [Time and billing](time-and-billing.md)).
  Abbreviation codes are not expanded: the model writes the narrative
  in full.
- **Events**: `create_event` applies the event form's rules (a start with
  no end runs an hour via `default_end_time()`, an end date on the start
  date is dropped, times must run forward within a day) and saves the
  event `Pending` so the calendar's default filter shows it. The matter
  is optional, as on the form; without one the event is the firm's. No
  assignee unless `assigned_to_me`, which matches how nearly every event
  in the firm's calendar is kept.
- **Contacts**: `create_contact` makes one address-book row, name-deduped
  (a same-named contact is reported and its details left alone), with
  the contact form's normalisation (`normalize_phone()`, lower-cased
  email). With `matter_id` it also puts the contact on the matter as a
  `Relationship`, which needs a `role` from `assignable_roles()` and a
  `group` from the matter's groups less the system Client group; both are
  resolved before anything is created, so a bad name leaves no orphan,
  and a refusal lists the names to choose from. `already_assigned()`
  stops a duplicate party row.

## Things that bite

- **The formatters are shared on purpose.** A change to a section
  formatter in `apps/ai/context.py` changes what the in-app chat, Claude
  and the JSON API see; a new section needs a `SECTIONS` entry and, if
  it carries money, a place in `FINANCIAL_SECTIONS`, and the `enum` in
  `read_matter`'s schema follows `SECTIONS` automatically.
- **Matter scope differs by API.** The matter functions serve open
  matters only; the practice-wide search lists matters of any status,
  because it is navigational.
- **The `resource` must match the URL the user typed.** The protected
  resource metadata says `https://host/mcp`; a proxy that changes the
  host, or a user who types a different one, breaks the token exchange.
  `PUBLIC_BASE_URL` pins it.
- **Registration is open.** It has to be: Claude registers before any
  user is involved. A client has no access until a user allows it, so
  the only thing registration can do is make rows; it is rate-limited
  per IP and rows nobody connected within a day are swept on the next
  registration.
- **Refresh reuse inside sixty seconds is tolerated.** Two of Claude's
  workers can refresh the same token at once; within
  `REFRESH_REUSE_GRACE` the second gets its own pair. Later reuse is
  treated as theft and revokes the connection (OAuth 2.1 section 4.3.1).
- **Email threads list most-recent-activity first** (2026-09-25), so the
  40k truncation drops the oldest; keep that order when touching
  `_format_email_threads()`.

How this replaced the per-user stdio script is recorded in
[Claude connects over a remote MCP server with OAuth](../../decisions/2026-10-30-claude-connects-over-remote-mcp.md).

## Related

- [Claude](../../admin/integrations/claude-desktop.md) for setup;
  [The archive and the intake chat](ai/context.md)
  for the matter tools and the search handler this reuses; [Drafts](drafts.md)
  for the companion that shares the API token.
