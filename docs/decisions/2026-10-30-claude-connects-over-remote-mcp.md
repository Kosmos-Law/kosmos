# Claude connects over a remote MCP server with OAuth (2026-10-30)

Kosmos serves its own remote MCP server at `/mcp`, behind an OAuth 2.1
authorization server that is also Kosmos's own (`apps/mcp`). A user
connects Claude by pasting one address into Claude's connector settings,
signing in to Kosmos in the browser and clicking Allow. This is the third
rung of the [packaging roadmap](claude-desktop-roadmap.md) recorded in
August, built two months later; the first rung, the per-user stdio script
(`tools/kosmos_notes_mcp.py`), is removed with it.

## What was wrong with the script

The script worked, and its tools are unchanged, but setting it up was a
page of instructions: install `uv`, download a file and keep it somewhere
permanent, open Claude Desktop's developer config, paste a JSON block
inside the right braces with the right commas, fix a path, restart. The
block carried the user's long-lived API token in clear. Every change to a
tool meant every user downloading the file again. It worked only in
Claude Desktop, not on claude.ai, the mobile apps or Cowork, and a Claude
Project could not be scoped to a matter other than by instructions. The
CourtListener connector, by contrast, is a button and a sign-in.

## What was decided

- **Kosmos is the MCP server and the authorization server.** Both are
  Django views; there is no second service to run, and the user's
  existing sign-in (email code or authenticator app) is the sign-in. A
  library such as django-oauth-toolkit was considered and not taken:
  the subset MCP needs (one grant, PKCE, dynamic registration, metadata
  documents, resource indicators, the `iss` parameter) is small, and
  the pieces that library lacks or configures awkwardly (RFC 7591
  registration, RFC 9728 metadata, loopback redirect matching) are the
  ones Claude depends on.
- **Two ways for Claude to identify itself, no pre-registration.**
  Dynamic client registration, as the 2025-06-18 MCP specification had
  it, and client ID metadata documents, as the current one prefers:
  Claude uses the second when the metadata advertises it, which spares
  a registration per connection. Nothing is entered in Claude's
  advanced OAuth settings; a firm never creates a client.
- **No scopes.** A token is the user's. What it reaches is what the user
  may reach, enforced by the same access functions as the application,
  so there is nothing a scope would add except a longer consent screen.
- **Tokens are hashed, rotated and revocable server-side.** Access
  tokens last an hour, refresh tokens ninety days and rotate on use with
  a sixty-second grace for Claude's concurrent workers. Settings →
  Claude lists connections and disconnects them; deactivating the user
  ends them all. The old `ApiToken` had no expiry and could only be
  rotated by hand.
- **The service layer is shared.** The views in `apps/ai/api.py` and
  `apps/search/api.py` were split into service functions and thin JSON
  views, and the MCP tools call the functions. The `X-Kosmos-Token` JSON
  APIs stay for scripts and the LibreOffice companion, unchanged in
  behaviour and tests.
- **Stateless transport.** One JSON-RPC message per POST, one JSON
  object back, no session id and no event stream. Nothing Kosmos does
  needs to push to the client; a stream would add a long-lived
  connection to gunicorn for no gain. If it is ever needed, the endpoint
  is where it goes.

## What it costs

- Kosmos must be reachable from Anthropic's servers over HTTPS. A firm
  on a private network cannot connect this way; the script needed only
  the user's own network. That firm is better served by a VPN in front
  of a public host than by keeping two transports.
- Registration is an open endpoint. It can make rows and nothing else;
  it is rate-limited and swept.
- The metadata-document path fetches a URL supplied in a request. The
  URL must be HTTPS to a named host, is fetched by a signed-in user's
  request only, is size-limited and cached.
