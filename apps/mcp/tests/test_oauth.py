"""The OAuth 2.1 authorization server: discovery, registration, the consent
screen, the code exchange with PKCE, refresh rotation and revocation."""

import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import Client
from django.utils import timezone

from apps.mcp.models import (
    REFRESH_REUSE_GRACE,
    McpAuthorizationCode,
    McpClient,
    McpConnection,
    McpToken,
)

from .conftest import CHALLENGE, CLAUDE_CALLBACK, VERIFIER, authorize_params

pytestmark = pytest.mark.django_db


def register(payload):
    return Client().post(
        "/mcp/oauth/register", json.dumps(payload), content_type="application/json"
    )


def exchange(**fields):
    return Client().post("/mcp/oauth/token", fields)


def consent(client, oauth_client, decision="allow", **overrides):
    """Answer the consent screen and return the redirect's query."""
    params = authorize_params(oauth_client, **overrides)
    response = client.post("/mcp/oauth/authorize", {**params, "decision": decision})
    assert response.status_code == 302
    location = urlsplit(response["Location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == CLAUDE_CALLBACK
    return {k: v[0] for k, v in parse_qs(location.query).items()}


class TestDiscovery:
    @pytest.mark.parametrize(
        "path",
        [
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
        ],
    )
    def test_protected_resource_metadata(self, path):
        body = Client().get(path).json()
        assert body["resource"] == "http://testserver/mcp"
        assert body["authorization_servers"] == ["http://testserver"]

    def test_authorization_server_metadata(self):
        body = Client().get("/.well-known/oauth-authorization-server").json()
        assert body["issuer"] == "http://testserver"
        assert body["authorization_endpoint"] == "http://testserver/mcp/oauth/authorize"
        assert body["token_endpoint"] == "http://testserver/mcp/oauth/token"
        assert body["registration_endpoint"] == "http://testserver/mcp/oauth/register"
        assert body["code_challenge_methods_supported"] == ["S256"]
        # Both of these together are what make Claude use its published
        # client identity instead of registering one per connection.
        assert body["client_id_metadata_document_supported"] is True
        assert "none" in body["token_endpoint_auth_methods_supported"]
        assert body["authorization_response_iss_parameter_supported"] is True

    def test_public_base_url_wins(self, settings):
        settings.PUBLIC_BASE_URL = "https://kosmos.example.com/"
        body = Client().get("/.well-known/oauth-protected-resource").json()
        assert body["resource"] == "https://kosmos.example.com/mcp"
        assert body["authorization_servers"] == ["https://kosmos.example.com"]


class TestRegistration:
    def test_public_client(self):
        response = register(
            {
                "client_name": "Claude",
                "redirect_uris": [CLAUDE_CALLBACK],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            }
        )
        assert response.status_code == 201
        body = response.json()
        assert "client_secret" not in body
        client = McpClient.objects.get(client_id=body["client_id"])
        assert client.name == "Claude"
        assert client.is_public
        assert client.redirect_uris == [CLAUDE_CALLBACK]

    def test_confidential_client_gets_a_secret(self):
        body = register(
            {
                "redirect_uris": [CLAUDE_CALLBACK],
                "token_endpoint_auth_method": "client_secret_post",
            }
        ).json()
        client = McpClient.objects.get(client_id=body["client_id"])
        assert client.check_secret(body["client_secret"])
        assert not client.check_secret("wrong")

    def test_loopback_redirect_is_allowed(self):
        response = register({"redirect_uris": ["http://localhost:3118/callback"]})
        assert response.status_code == 201

    @pytest.mark.parametrize(
        "uri",
        ["http://evil.example.com/cb", "https://claude.ai/cb#frag", "not a url", 7],
    )
    def test_bad_redirect_is_refused(self, uri):
        response = register({"redirect_uris": [uri]})
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_redirect_uri"

    def test_missing_redirects_is_refused(self):
        assert register({"client_name": "x"}).status_code == 400
        assert register(["not", "an", "object"]).status_code == 400

    def test_unconnected_old_clients_are_swept(self, oauth_client, connection):
        stale = McpClient.objects.create(client_id="stale", redirect_uris=[])
        McpClient.objects.filter(pk__in=[stale.pk, oauth_client.pk]).update(
            created_at=timezone.now() - timedelta(days=3)
        )
        register({"redirect_uris": [CLAUDE_CALLBACK]})
        assert not McpClient.objects.filter(pk=stale.pk).exists()
        # The connected one stays, however old.
        assert McpClient.objects.filter(pk=oauth_client.pk).exists()


class TestAuthorize:
    def test_anonymous_is_sent_to_sign_in_and_back(self, oauth_client):
        response = Client().get("/mcp/oauth/authorize", authorize_params(oauth_client))
        assert response.status_code == 302
        assert response["Location"].startswith(
            "/accounts/login/?next=/mcp/oauth/authorize"
        )

    def test_consent_screen_names_the_client(self, client, oauth_client):
        response = client.get("/mcp/oauth/authorize", authorize_params(oauth_client))
        assert response.status_code == 200
        page = response.content.decode()
        assert "Connect Claude to Kosmos" in page
        assert "claude.ai" in page
        assert 'name="decision"' in page

    def test_unknown_client_is_a_page_not_a_redirect(self, client, oauth_client):
        response = client.get(
            "/mcp/oauth/authorize", authorize_params(oauth_client, client_id="nope")
        )
        assert response.status_code == 400
        assert "Unknown client" in response.content.decode()

    def test_unregistered_redirect_is_a_page_not_a_redirect(self, client, oauth_client):
        response = client.get(
            "/mcp/oauth/authorize",
            authorize_params(oauth_client, redirect_uri="https://evil.example.com/cb"),
        )
        assert response.status_code == 400

    def test_missing_pkce_is_an_error_redirect(self, client, oauth_client):
        response = client.get(
            "/mcp/oauth/authorize",
            authorize_params(oauth_client, code_challenge=None),
        )
        assert response.status_code == 302
        query = parse_qs(urlsplit(response["Location"]).query)
        assert query["error"] == ["invalid_request"]
        assert query["state"] == ["s3cret-state"]
        assert query["iss"] == ["http://testserver"]

    def test_plain_pkce_method_is_refused(self, client, oauth_client):
        response = client.get(
            "/mcp/oauth/authorize",
            authorize_params(oauth_client, code_challenge_method="plain"),
        )
        assert "error=invalid_request" in response["Location"]

    def test_foreign_resource_is_refused(self, client, oauth_client):
        response = client.get(
            "/mcp/oauth/authorize",
            authorize_params(oauth_client, resource="https://other.example.com/mcp"),
        )
        assert "error=invalid_target" in response["Location"]

    def test_allow_issues_a_code(self, client, oauth_client, user):
        query = consent(client, oauth_client)
        assert query["state"] == "s3cret-state"
        assert query["iss"] == "http://testserver"
        assert query["code"].startswith("kmc_")
        row = McpAuthorizationCode.objects.get()
        assert row.user == user
        assert row.client == oauth_client
        assert row.code_challenge == CHALLENGE

    def test_deny_redirects_with_access_denied(self, client, oauth_client):
        query = consent(client, oauth_client, decision="deny")
        assert query["error"] == "access_denied"
        assert not McpAuthorizationCode.objects.exists()

    def test_loopback_redirect_matches_on_any_port(self, client):
        code_client = McpClient.objects.create(
            client_id="https://claude.ai/oauth/claude-code-client-metadata",
            name="Claude Code",
            redirect_uris=["http://localhost/callback", "http://127.0.0.1/callback"],
            is_metadata_document=True,
        )
        response = client.get(
            "/mcp/oauth/authorize",
            authorize_params(
                code_client, redirect_uri="http://localhost:3118/callback"
            ),
        )
        assert response.status_code == 200
        assert "on your own computer" in response.content.decode()
        response = client.get(
            "/mcp/oauth/authorize",
            authorize_params(code_client, redirect_uri="http://localhost:3118/other"),
        )
        assert response.status_code == 400


class FakeResponse:
    def __init__(self, document, status_code=200):
        self.status_code = status_code
        self.content = json.dumps(document).encode()

    def json(self):
        return json.loads(self.content)


class TestClientMetadataDocuments:
    URL = "https://claude.ai/oauth/claude-metadata.json"

    def test_document_is_fetched_validated_and_cached(self, client, monkeypatch):
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            return FakeResponse(
                {
                    "client_id": self.URL,
                    "client_name": "Claude",
                    "redirect_uris": [CLAUDE_CALLBACK],
                    "token_endpoint_auth_method": "none",
                }
            )

        monkeypatch.setattr("apps.mcp.oauth.requests.get", fake_get)
        stub = McpClient(client_id=self.URL)
        response = client.get("/mcp/oauth/authorize", authorize_params(stub))
        assert response.status_code == 200
        assert "Connect Claude to Kosmos" in response.content.decode()
        row = McpClient.objects.get(client_id=self.URL)
        assert row.is_metadata_document and row.is_public
        assert row.redirect_uris == [CLAUDE_CALLBACK]

        client.get("/mcp/oauth/authorize", authorize_params(stub))
        assert calls == [self.URL]

    def test_document_naming_another_client_id_is_refused(self, client, monkeypatch):
        monkeypatch.setattr(
            "apps.mcp.oauth.requests.get",
            lambda url, **kw: FakeResponse(
                {
                    "client_id": "https://claude.ai/other.json",
                    "client_name": "Claude",
                    "redirect_uris": [CLAUDE_CALLBACK],
                }
            ),
        )
        stub = McpClient(client_id=self.URL)
        response = client.get("/mcp/oauth/authorize", authorize_params(stub))
        assert response.status_code == 400
        assert not McpClient.objects.filter(client_id=self.URL).exists()

    def test_unreachable_document_is_refused(self, client, monkeypatch):
        monkeypatch.setattr(
            "apps.mcp.oauth.requests.get", lambda url, **kw: FakeResponse({}, 404)
        )
        stub = McpClient(client_id=self.URL)
        response = client.get("/mcp/oauth/authorize", authorize_params(stub))
        assert response.status_code == 400

    @pytest.mark.parametrize(
        "client_id",
        [
            "https://claude.ai",
            "https://claude.ai/",
            "http://claude.ai/x.json",
            "https://127.0.0.1/x.json",
            "https://localhost/x.json",
        ],
    )
    def test_what_is_not_a_document_url(self, client, client_id):
        """Anything that is not an HTTPS URL to a named host with a path is
        looked up as a registered client and found unknown; nothing is
        fetched."""
        stub = McpClient(client_id=client_id)
        response = client.get("/mcp/oauth/authorize", authorize_params(stub))
        assert response.status_code == 400
        assert "Unknown client" in response.content.decode()


class TestTokenExchange:
    def test_code_for_tokens(self, client, oauth_client, user):
        code = consent(client, oauth_client)["code"]
        response = exchange(
            grant_type="authorization_code",
            code=code,
            redirect_uri=CLAUDE_CALLBACK,
            client_id=oauth_client.client_id,
            code_verifier=VERIFIER,
            resource="http://testserver/mcp",
        )
        assert response.status_code == 200
        assert response["Cache-Control"] == "no-store"
        body = response.json()
        assert body["token_type"] == "Bearer"
        assert body["expires_in"] == 3600
        connection = McpConnection.objects.get()
        assert connection.user == user and connection.client == oauth_client
        assert McpToken.by_access_token(body["access_token"]) == connection
        assert not McpAuthorizationCode.objects.exists()

    def test_wrong_verifier_is_invalid_grant(self, client, oauth_client):
        code = consent(client, oauth_client)["code"]
        response = exchange(
            grant_type="authorization_code",
            code=code,
            redirect_uri=CLAUDE_CALLBACK,
            client_id=oauth_client.client_id,
            code_verifier="y" * 43,
        )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_grant"
        assert not McpConnection.objects.exists()
        # The code was consumed by the attempt: it cannot be tried again.
        assert not McpAuthorizationCode.objects.exists()

    def test_wrong_redirect_uri_is_invalid_grant(self, client, oauth_client):
        code = consent(client, oauth_client)["code"]
        response = exchange(
            grant_type="authorization_code",
            code=code,
            redirect_uri="https://claude.com/api/mcp/auth_callback",
            client_id=oauth_client.client_id,
            code_verifier=VERIFIER,
        )
        assert response.json()["error"] == "invalid_grant"

    def test_code_cannot_be_redeemed_twice(self, client, oauth_client):
        code = consent(client, oauth_client)["code"]
        fields = dict(
            grant_type="authorization_code",
            code=code,
            redirect_uri=CLAUDE_CALLBACK,
            client_id=oauth_client.client_id,
            code_verifier=VERIFIER,
        )
        assert exchange(**fields).status_code == 200
        assert exchange(**fields).json()["error"] == "invalid_grant"

    def test_expired_code_is_refused(self, client, oauth_client):
        code = consent(client, oauth_client)["code"]
        McpAuthorizationCode.objects.update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        response = exchange(
            grant_type="authorization_code",
            code=code,
            redirect_uri=CLAUDE_CALLBACK,
            client_id=oauth_client.client_id,
            code_verifier=VERIFIER,
        )
        assert response.json()["error"] == "invalid_grant"

    def test_another_clients_code_is_refused(self, client, oauth_client):
        other = McpClient.objects.create(
            client_id="other", name="Other", redirect_uris=[CLAUDE_CALLBACK]
        )
        code = consent(client, oauth_client)["code"]
        response = exchange(
            grant_type="authorization_code",
            code=code,
            redirect_uri=CLAUDE_CALLBACK,
            client_id=other.client_id,
            code_verifier=VERIFIER,
        )
        assert response.json()["error"] == "invalid_grant"

    def test_confidential_client_must_present_its_secret(self, client):
        body = register(
            {
                "redirect_uris": [CLAUDE_CALLBACK],
                "token_endpoint_auth_method": "client_secret_post",
            }
        ).json()
        confidential = McpClient.objects.get(client_id=body["client_id"])
        code = consent(client, confidential)["code"]
        fields = dict(
            grant_type="authorization_code",
            code=code,
            redirect_uri=CLAUDE_CALLBACK,
            client_id=confidential.client_id,
            code_verifier=VERIFIER,
        )
        refused = exchange(**fields)
        assert refused.status_code == 401
        assert refused.json()["error"] == "invalid_client"
        accepted = exchange(**fields, client_secret=body["client_secret"])
        assert accepted.status_code == 200

    def test_unknown_grant_type(self, oauth_client):
        response = exchange(grant_type="password", client_id=oauth_client.client_id)
        assert response.json()["error"] == "unsupported_grant_type"


class TestRefresh:
    def issue(self, connection):
        access, refresh, _ = McpToken.issue(connection)
        return access, refresh

    def test_refresh_rotates(self, connection, oauth_client):
        access, refresh = self.issue(connection)
        response = exchange(
            grant_type="refresh_token",
            refresh_token=refresh,
            client_id=oauth_client.client_id,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["refresh_token"] != refresh
        assert McpToken.by_access_token(body["access_token"]) == connection
        # The old access token lives out its hour; a request in flight on
        # it is not failed by the refresh.
        assert McpToken.by_access_token(access) == connection
        assert McpConnection.objects.count() == 1

    def test_reuse_within_grace_issues_another_pair(self, connection, oauth_client):
        _access, refresh = self.issue(connection)
        fields = dict(
            grant_type="refresh_token",
            refresh_token=refresh,
            client_id=oauth_client.client_id,
        )
        first = exchange(**fields).json()
        second = exchange(**fields).json()
        assert first["access_token"] != second["access_token"]
        assert McpToken.by_access_token(second["access_token"]) == connection

    def test_reuse_after_grace_revokes_the_connection(self, connection, oauth_client):
        _access, refresh = self.issue(connection)
        fields = dict(
            grant_type="refresh_token",
            refresh_token=refresh,
            client_id=oauth_client.client_id,
        )
        exchange(**fields)
        McpToken.objects.filter(refresh_used_at__isnull=False).update(
            refresh_used_at=timezone.now() - REFRESH_REUSE_GRACE - timedelta(seconds=1)
        )
        response = exchange(**fields)
        assert response.json()["error"] == "invalid_grant"
        assert not McpConnection.objects.exists()

    def test_expired_refresh_token(self, connection, oauth_client):
        _access, refresh = self.issue(connection)
        McpToken.objects.update(refresh_expires_at=timezone.now() - timedelta(days=1))
        response = exchange(
            grant_type="refresh_token",
            refresh_token=refresh,
            client_id=oauth_client.client_id,
        )
        assert response.json()["error"] == "invalid_grant"

    def test_inactive_user_cannot_refresh(self, connection, oauth_client, user):
        _access, refresh = self.issue(connection)
        user.is_active = False
        user.save()
        response = exchange(
            grant_type="refresh_token",
            refresh_token=refresh,
            client_id=oauth_client.client_id,
        )
        assert response.json()["error"] == "invalid_grant"


class TestRevoke:
    def test_either_token_ends_the_connection(self, connection, oauth_client):
        access, refresh, _ = McpToken.issue(connection)
        response = Client().post(
            "/mcp/oauth/revoke", {"token": refresh, "client_id": oauth_client.client_id}
        )
        assert response.status_code == 200
        assert not McpConnection.objects.exists()
        assert McpToken.by_access_token(access) is None

    def test_unknown_token_is_still_200(self, oauth_client):
        response = Client().post(
            "/mcp/oauth/revoke",
            {"token": "nothing", "client_id": oauth_client.client_id},
        )
        assert response.status_code == 200
