"""The remote MCP server and its authorization server. The well-known
documents sit at the site root, where the specifications put them; the
endpoint is /mcp (what the user pastes into Claude) and the OAuth
endpoints are under it."""

from django.urls import path

from . import oauth, server

app_name = "mcp"

urlpatterns = [
    path(
        ".well-known/oauth-protected-resource",
        oauth.protected_resource_metadata,
        name="protected-resource",
    ),
    path(
        ".well-known/oauth-protected-resource/mcp",
        oauth.protected_resource_metadata,
        name="protected-resource-mcp",
    ),
    path(
        ".well-known/oauth-authorization-server",
        oauth.authorization_server_metadata,
        name="authorization-server",
    ),
    path("mcp", server.endpoint, name="endpoint"),
    path("mcp/", server.endpoint),
    path("mcp/oauth/register", oauth.register, name="register"),
    path("mcp/oauth/authorize", oauth.authorize, name="authorize"),
    path("mcp/oauth/token", oauth.token, name="token"),
    path("mcp/oauth/revoke", oauth.revoke, name="revoke"),
]
