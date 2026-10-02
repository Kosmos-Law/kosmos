# Claude Desktop: packaging roadmap

Recorded 2026-08-14 alongside the first MCP server
([MCP server and JSON APIs](../dev/subsystems/mcp.md)).

The API and tool semantics are the product; transport and auth are
packaging. The current server is rung 1: a single-file stdio script each
user downloads and runs with uv.

**Rung 2:** package the same server as an MCP bundle (`.mcpb`) for
one-click Desktop install. Desktop ships a Node runtime, not Python, so
that client is a thin TypeScript port; keep the script dumb so the port
stays trivial.

**Rung 3:** remote MCP (streamable HTTP) served by Django itself behind
OAuth 2.1 (django-oauth-toolkit; Claude accepts a manually issued client
id/secret, so dynamic client registration can wait). No local install,
works on claude.ai web and mobile, and offboarding is a server-side
revoke.
