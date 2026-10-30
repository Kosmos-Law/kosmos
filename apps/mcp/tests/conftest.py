"""Fixtures for the remote MCP server: the case fixtures (a user, a matter,
a document, a highlight, a fact), plus a registered client, a connection
and the PKCE pair the OAuth tests exchange."""

import base64
import hashlib
import json

import pytest
from django.core.cache import cache
from django.test import Client

from apps.case.tests.conftest import *  # noqa: F401,F403
from apps.mcp.models import McpClient, McpConnection, McpToken

CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "x" * 43
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest())
    .rstrip(b"=")
    .decode()
)


@pytest.fixture(autouse=True)
def _request_derived_base_url(settings):
    """The tests' base URL is the test client's host, whatever the local
    config/.env says the public address is."""
    settings.PUBLIC_BASE_URL = ""
    cache.clear()


@pytest.fixture
def oauth_client(db):
    """A public client, as Claude registers itself."""
    return McpClient.objects.create(
        client_id="claude-test-client",
        name="Claude",
        redirect_uris=[CLAUDE_CALLBACK],
    )


@pytest.fixture
def connection(user, oauth_client):
    return McpConnection.objects.create(user=user, client=oauth_client)


@pytest.fixture
def access_token(connection):
    access, _refresh, _expires = McpToken.issue(connection)
    return access


def authorize_params(oauth_client, **overrides):
    params = {
        "client_id": oauth_client.client_id,
        "redirect_uri": CLAUDE_CALLBACK,
        "response_type": "code",
        "state": "s3cret-state",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "resource": "http://testserver/mcp",
    }
    params.update(overrides)
    return {k: v for k, v in params.items() if v is not None}


def rpc(token, method, params=None, message_id=1, **headers):
    """Post one JSON-RPC request to the MCP endpoint as a bearer."""
    body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if message_id is not None:
        body["id"] = message_id
    extra = {"HTTP_ACCEPT": "application/json, text/event-stream", **headers}
    if token:
        extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return Client().post(
        "/mcp", json.dumps(body), content_type="application/json", **extra
    )
