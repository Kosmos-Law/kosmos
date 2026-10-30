# Claude

Claude can work with Kosmos directly: claude.ai on the web, Claude
Desktop, the mobile apps, Cowork and Claude Code all connect the same
way. For any open matter the user can access, Claude reads the full
record (contacts, rates, activity, events, tasks, proceedings,
settlement, documents, highlights, timeline, witnesses, synced emails,
earlier AI conversations, invoices) and searches across the practice.
Writes are narrow and deliberate: create-only timeline facts, witnesses
and tasks. Access is per user: Claude signs in as the user, through
Kosmos's own sign-in, and sees exactly what that user can see.
Deactivating the user, or disconnecting under Settings → Claude, ends the
access at once.

Kosmos is a remote MCP server (`/mcp`) with its own OAuth 2.1
authorization server. Nothing is configured on the server for it, and
nothing is installed on the user's machine. How the pieces fit together
is in the developer guide: [MCP server and JSON APIs](../../dev/subsystems/mcp.md).

## What the server needs

- **HTTPS at a public address.** Claude's connections come from
  Anthropic's servers, not from the user's computer, so the Kosmos host
  must be reachable from the internet (from Anthropic's published egress
  range, `160.79.104.0/21`, if a firewall limits who may connect). A
  server on a private network or behind a VPN cannot be connected, and
  the browser that signs the user in must reach it too.
- **The right public address.** The connector URL on the Settings page
  is built from the request, or from `PUBLIC_BASE_URL` when that is set.
  Behind a proxy that rewrites the host, set `PUBLIC_BASE_URL` to the
  address users type, or the addresses in the OAuth metadata will not
  match and the sign-in fails.
- **The well-known paths at the root.** `/.well-known/oauth-protected-resource`
  and `/.well-known/oauth-authorization-server` are served by Kosmos; a
  reverse proxy that routes `/.well-known/` elsewhere (for certificate
  renewal, say) must pass these two on. A rule that refuses hidden
  paths (`location ~ /\.` in nginx) catches them too; the shipped
  `kosmos-security.conf` puts a `location ^~ /.well-known/oauth-`
  before its own.

## User setup

1. In Kosmos, open **Settings → Claude** and copy the connector address
   (`https://<your host>/mcp`).
2. In Claude, open Settings, then Connectors, and choose **Add custom
   connector**. Name it Kosmos, paste the address as the server URL, and
   leave the OAuth settings as they are.
3. Click **Connect**. The browser opens Kosmos: sign in if asked (the
   usual email code or authenticator app), and click **Allow**.
4. Back in Claude, the Kosmos tools are available in every conversation,
   on every device signed in to that Claude account.

In Claude Code, the same connection is
`claude mcp add --transport http kosmos https://<your host>/mcp` followed
by `/mcp` in the session to sign in.

A connection stays until the user disconnects it (Settings → Claude, or
in Claude's connector settings), an administrator deactivates the user,
or it goes ninety days unused. Each connection is listed on the Settings
page with when it was made and last used.

## Scoping a Claude Project to a matter

Matter scoping is conversational: the tools take the matter as a
parameter, and a per-matter Claude Project carries it in its
instructions, e.g.:

> This project concerns the Kosmos matter "Rivera v. Northside Logistics".
> Resolve it once with find_matter, then pass its matter_id to the
> read_matter, search_matter, and add_fact tools.

## What Claude can write

Two write surfaces, both create-only, neither destructive:

- **Timeline facts and witnesses**: Claude can add them to a matter, with
  the same validation the in-app chat applies.
- **Tasks**: Claude can add tasks, assigned to the user who connected.

## Troubleshooting

- **"Couldn't reach the MCP server"** when adding the connector: Claude
  could not fetch `https://<host>/mcp` or the well-known documents from
  Anthropic's servers. Check that the host is public, that the
  certificate is valid, and that the proxy passes `/.well-known/` on.
  `curl -i https://<host>/mcp` from outside should answer `401` with a
  `WWW-Authenticate` header.
- **"Couldn't register with Kosmos's sign-in service"**: Claude could
  not read the well-known documents, fell back to `/register` at the
  root, and found nothing there. `curl -i
  https://<host>/.well-known/oauth-authorization-server` should answer
  `200` with JSON; a `403` from nginx means a hidden-files rule is in
  front of it (see the well-known note above).
- **The sign-in page says the connection cannot be made**: the
  application's redirect address is not one it registered, or its
  client id is unknown. Remove the connector in Claude and add it again.
- **The sign-in loops or lands on the Dash**: the address Claude used
  does not match the one Kosmos believes is its own. Set
  `PUBLIC_BASE_URL`.
- **Tools fail with "Your Kosmos account does not have financial
  access"**: as in the application, the ledger, trust and rates need the
  Financial permission.
