"""The OAuth 2.1 authorization server behind the remote MCP server.

Claude (claude.ai, Claude Desktop, the mobile apps, Claude Code) connects
to Kosmos the way it connects to any remote MCP server: it reads the
protected resource metadata, finds this authorization server in it, gets a
client id, sends the user to the consent screen here, and swaps the code
it is handed for tokens. The user signs in to Kosmos as usual (the sign-in
view carries the authorization request through ``next``), clicks Allow
once, and is connected. Nothing is configured on the server, and nothing
is installed on the user's machine.

What is implemented, and from which specification:

- Protected resource metadata (RFC 9728) at
  ``/.well-known/oauth-protected-resource`` and the same under ``/mcp``.
- Authorization server metadata (RFC 8414) at
  ``/.well-known/oauth-authorization-server``; the issuer is the site's
  base URL.
- Client registration two ways: dynamic registration (RFC 7591) at
  ``/mcp/oauth/register``, and client ID metadata documents, where the
  client id is an HTTPS URL whose document names the client and its
  redirect URIs. Claude prefers the second when the metadata advertises
  it, which spares a registration per connection.
- The authorization code grant with PKCE (S256, required of every client)
  and the ``iss`` response parameter (RFC 9207); refresh tokens, rotated
  on use (OAuth 2.1 section 4.3.1); revocation (RFC 7009); resource
  indicators (RFC 8707) checked against this server's MCP URL.

There are no scopes: a token is the user's, and what it reaches is what
the user may reach in Kosmos. Revoking is server-side, from Settings >
Claude, and deactivating the user ends every token at once.
"""

import base64
import hashlib
import ipaddress
import json
import logging
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode, urlsplit

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from utils.ratelimit import rate_limited

from .models import McpAuthorizationCode, McpClient, McpConnection, McpToken, digest

logger = logging.getLogger(__name__)

MCP_PATH = "/mcp"
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1", "[::1]")
METADATA_DOCUMENT_CACHE = 60 * 60
METADATA_DOCUMENT_MAX_BYTES = 64 * 1024
# Registrations nobody authorized within a day were a client that never
# connected (Claude registers afresh each time a connection is set up).
UNUSED_CLIENT_DAYS = 1


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------


def base_url(request):
    """The site's public base URL, scheme and host, no trailing slash.
    PUBLIC_BASE_URL when it is set (behind a proxy that is the one true
    address); otherwise the address the request came in on."""
    if settings.PUBLIC_BASE_URL:
        return settings.PUBLIC_BASE_URL.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def mcp_url(request):
    """The MCP endpoint's canonical URL: what the user pastes into Claude,
    and the ``resource`` every token is for."""
    return base_url(request) + MCP_PATH


def resource_metadata_url(request):
    return base_url(request) + "/.well-known/oauth-protected-resource" + MCP_PATH


def _same_resource(request, resource):
    """Whether a ``resource`` parameter names this MCP server, allowing for
    a trailing slash and the case of the scheme and host."""
    wanted = urlsplit(mcp_url(request))
    given = urlsplit(resource.strip())
    return (
        given.scheme.lower() == wanted.scheme.lower()
        and given.netloc.lower() == wanted.netloc.lower()
        and given.path.rstrip("/") == wanted.path
        and not given.query
        and not given.fragment
    )


# ---------------------------------------------------------------------------
# Metadata documents
# ---------------------------------------------------------------------------


def _no_store(response):
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    return response


@require_GET
def protected_resource_metadata(request):
    """RFC 9728. Claude reads this to learn where to send the user; the
    ``resource`` must equal the URL the user entered for the connector."""
    return JsonResponse(
        {
            "resource": mcp_url(request),
            "authorization_servers": [base_url(request)],
            "bearer_methods_supported": ["header"],
            "resource_name": "Kosmos",
            "resource_documentation": "https://kosmos.law/docs/admin/integrations/claude-desktop/",
        }
    )


@require_GET
def authorization_server_metadata(request):
    """RFC 8414. ``client_id_metadata_document_supported`` together with
    ``none`` among the token endpoint auth methods is what makes Claude
    identify itself by its published metadata document rather than
    register a client per connection."""
    base = base_url(request)
    auth_methods = ["none", "client_secret_post", "client_secret_basic"]
    return JsonResponse(
        {
            "issuer": base,
            "authorization_endpoint": base + "/mcp/oauth/authorize",
            "token_endpoint": base + "/mcp/oauth/token",
            "registration_endpoint": base + "/mcp/oauth/register",
            "revocation_endpoint": base + "/mcp/oauth/revoke",
            "response_types_supported": ["code"],
            "response_modes_supported": ["query"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": auth_methods,
            "revocation_endpoint_auth_methods_supported": auth_methods,
            "code_challenge_methods_supported": ["S256"],
            "client_id_metadata_document_supported": True,
            "authorization_response_iss_parameter_supported": True,
            "service_documentation": "https://kosmos.law/docs/admin/integrations/claude-desktop/",
        }
    )


# ---------------------------------------------------------------------------
# Clients: registration, metadata documents, redirect URIs
# ---------------------------------------------------------------------------


def _is_loopback(parts):
    return parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS


def valid_redirect_uri(uri):
    """OAuth 2.1 section 1.5: HTTPS, or plain HTTP to the loopback address
    (Claude Code listens on one), and never a fragment."""
    if not isinstance(uri, str) or len(uri) > 2048:
        return False
    try:
        parts = urlsplit(uri)
    except ValueError:
        return False
    if parts.fragment or not parts.netloc:
        return False
    return parts.scheme == "https" or _is_loopback(parts)


def redirect_uri_allowed(uri, registered):
    """Exact match against the registered URIs, except that a loopback URI
    matches on any port (RFC 8252 section 7.3): Claude Code picks a free
    port for each session, and its metadata document names no port."""
    if uri in registered:
        return True
    try:
        given = urlsplit(uri)
    except ValueError:
        return False
    if not _is_loopback(given):
        return False
    for candidate in registered:
        try:
            other = urlsplit(candidate)
        except ValueError:
            continue
        if (
            _is_loopback(other)
            and other.hostname == given.hostname
            and other.path == given.path
            and other.query == given.query
        ):
            return True
    return False


def is_metadata_document_id(client_id):
    """A client id that is a URL is a client ID metadata document: HTTPS,
    a host that is a name (not an address or the loopback), and a path."""
    try:
        parts = urlsplit(client_id)
    except ValueError:
        return False
    if parts.scheme != "https" or not parts.hostname or parts.fragment:
        return False
    if parts.path in ("", "/"):
        return False
    if parts.hostname in LOOPBACK_HOSTS:
        return False
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        return True
    return False


class ClientError(Exception):
    """A client that cannot be used, with the OAuth error code."""

    def __init__(self, error, description):
        super().__init__(description)
        self.error = error
        self.description = description


def fetch_metadata_document(url):
    """The client's metadata document, as a dict, from the cache or the
    web. Raises ClientError when it cannot be fetched or is not a client
    metadata document for this URL."""
    key = "mcp:cimd:" + digest(url)
    document = cache.get(key)
    if document is None:
        try:
            response = requests.get(
                url,
                headers={"Accept": "application/json"},
                timeout=5,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise ClientError(
                "invalid_client", f"The client's metadata could not be fetched: {exc}"
            )
        if response.status_code != 200:
            raise ClientError(
                "invalid_client",
                f"The client's metadata URL answered {response.status_code}.",
            )
        if len(response.content) > METADATA_DOCUMENT_MAX_BYTES:
            raise ClientError("invalid_client", "The client's metadata is too large.")
        try:
            document = response.json()
        except ValueError:
            raise ClientError("invalid_client", "The client's metadata is not JSON.")
        if not isinstance(document, dict):
            raise ClientError("invalid_client", "The client's metadata is not JSON.")
        cache.set(key, document, METADATA_DOCUMENT_CACHE)
    if document.get("client_id") != url:
        raise ClientError(
            "invalid_client", "The client's metadata does not name its own URL."
        )
    uris = document.get("redirect_uris")
    if (
        not isinstance(uris, list)
        or not uris
        or not all(valid_redirect_uri(u) for u in uris)
    ):
        raise ClientError(
            "invalid_client", "The client's metadata has no usable redirect URIs."
        )
    if document.get("token_endpoint_auth_method", "none") != "none":
        raise ClientError(
            "invalid_client",
            "Only public clients are supported through metadata documents.",
        )
    return document


def resolve_client(client_id):
    """The client for ``client_id``: a registered row, or a metadata
    document fetched and cached as one. Raises ClientError."""
    if not client_id:
        raise ClientError("invalid_client", "client_id is required.")
    if is_metadata_document_id(client_id):
        document = fetch_metadata_document(client_id)
        client, _ = McpClient.objects.update_or_create(
            client_id=client_id,
            defaults={
                "name": str(document.get("client_name") or "")[:255]
                or urlsplit(client_id).hostname,
                "client_uri": str(document.get("client_uri") or "")[:512],
                "redirect_uris": document["redirect_uris"],
                "secret_hash": "",
                "is_metadata_document": True,
            },
        )
        return client
    client = McpClient.objects.filter(client_id=client_id).first()
    if client is None:
        raise ClientError("invalid_client", "Unknown client.")
    return client


@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    """RFC 7591 dynamic client registration. Open, as the protocol needs,
    but a client has no access until a user allows it on the consent
    screen, so the only thing registration can do is make rows: it is
    rate-limited, and rows nobody connected are swept."""
    if rate_limited(request, "mcp-register", limit=30, window=3600):
        return JsonResponse(
            {"error": "invalid_client_metadata", "error_description": "Slow down."},
            status=429,
        )
    try:
        metadata = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        metadata = None
    if not isinstance(metadata, dict):
        return _registration_error("Body must be a JSON object.")
    uris = metadata.get("redirect_uris")
    if not isinstance(uris, list) or not uris:
        return _registration_error("redirect_uris is required.", "invalid_redirect_uri")
    if len(uris) > 20 or not all(valid_redirect_uri(u) for u in uris):
        return _registration_error(
            "Every redirect URI must be https, or http to the loopback address.",
            "invalid_redirect_uri",
        )
    grant_types = metadata.get("grant_types") or ["authorization_code"]
    if not set(grant_types) <= {"authorization_code", "refresh_token"}:
        return _registration_error("Only the authorization_code grant is offered.")
    auth_method = metadata.get("token_endpoint_auth_method") or "none"
    if auth_method not in ("none", "client_secret_post", "client_secret_basic"):
        return _registration_error("Unsupported token_endpoint_auth_method.")

    McpClient.objects.filter(
        is_metadata_document=False,
        mcpconnection__isnull=True,
        created_at__lt=timezone.now() - timedelta(days=UNUSED_CLIENT_DAYS),
    ).delete()

    secret = "" if auth_method == "none" else secrets.token_urlsafe(32)
    client = McpClient.objects.create(
        client_id=secrets.token_urlsafe(24),
        name=str(metadata.get("client_name") or "An application")[:255],
        client_uri=str(metadata.get("client_uri") or "")[:512],
        redirect_uris=uris,
        secret_hash=digest(secret) if secret else "",
    )
    body = {
        "client_id": client.client_id,
        "client_id_issued_at": int(client.created_at.timestamp()),
        "client_name": client.name,
        "redirect_uris": uris,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": auth_method,
    }
    if client.client_uri:
        body["client_uri"] = client.client_uri
    if secret:
        body["client_secret"] = secret
        body["client_secret_expires_at"] = 0
    return _no_store(JsonResponse(body, status=201))


def _registration_error(description, error="invalid_client_metadata"):
    return JsonResponse({"error": error, "error_description": description}, status=400)


# ---------------------------------------------------------------------------
# The authorization endpoint and consent screen
# ---------------------------------------------------------------------------

AUTHORIZATION_FIELDS = (
    "client_id",
    "redirect_uri",
    "response_type",
    "state",
    "code_challenge",
    "code_challenge_method",
    "resource",
    "scope",
)


class AuthorizationRequest:
    """One parsed authorization request. ``client`` and ``redirect_uri``
    are trusted once set; ``error`` is what to send back to the client,
    or None when the request is good."""

    def __init__(self, request, params):
        self.params = {k: (params.get(k) or "").strip() for k in AUTHORIZATION_FIELDS}
        self.client = resolve_client(self.params["client_id"])
        uri = self.params["redirect_uri"]
        if not uri or not redirect_uri_allowed(uri, self.client.redirect_uris):
            raise ClientError(
                "invalid_request",
                "The redirect URI is not one this client registered.",
            )
        self.redirect_uri = uri
        self.error = None
        if self.params["response_type"] != "code":
            self.error = ("unsupported_response_type", "Only response_type=code.")
        elif not self.params["code_challenge"]:
            self.error = ("invalid_request", "PKCE (code_challenge) is required.")
        elif self.params["code_challenge_method"] not in ("S256",):
            self.error = ("invalid_request", "Only code_challenge_method=S256.")
        elif self.params["resource"] and not _same_resource(
            request, self.params["resource"]
        ):
            self.error = ("invalid_target", "The resource is not this server.")

    def redirect(self, request, **extra):
        query = {"iss": base_url(request), **extra}
        if self.params["state"]:
            query["state"] = self.params["state"]
        joiner = "&" if urlsplit(self.redirect_uri).query else "?"
        return redirect(self.redirect_uri + joiner + urlencode(query))

    def redirect_error(self, request, error, description):
        return self.redirect(request, error=error, error_description=description)


def _authorization_error_page(request, description):
    """A request that cannot be answered through the client's redirect URI
    (unknown client, unregistered redirect) ends on a page: the user must
    not be sent anywhere the request chose."""
    return render(
        request,
        "mcp/error.html",
        {"description": description},
        status=400,
    )


@login_required
@require_http_methods(["GET", "POST"])
def authorize(request):
    """The consent screen. GET shows it; POST answers it. Both parse the
    whole authorization request, so the POST cannot be bent to a redirect
    URI the GET did not validate."""
    params = request.POST if request.method == "POST" else request.GET
    try:
        auth = AuthorizationRequest(request, params)
    except ClientError as exc:
        return _authorization_error_page(request, exc.description)
    if auth.error:
        return auth.redirect_error(request, *auth.error)

    if request.method == "GET":
        return render(
            request,
            "mcp/authorize.html",
            {
                "client": auth.client,
                "redirect_host": urlsplit(auth.redirect_uri).hostname,
                "loopback_only": all(
                    _is_loopback(urlsplit(u)) for u in auth.client.redirect_uris
                ),
                "fields": auth.params,
            },
        )

    if request.POST.get("decision") != "allow":
        return auth.redirect_error(request, "access_denied", "The user declined.")
    code = McpAuthorizationCode.issue(
        client=auth.client,
        user=request.user,
        redirect_uri=auth.redirect_uri,
        code_challenge=auth.params["code_challenge"],
        resource=auth.params["resource"],
    )
    return auth.redirect(request, code=code)


# ---------------------------------------------------------------------------
# The token and revocation endpoints
# ---------------------------------------------------------------------------


def _token_error(error, description, status=400):
    response = JsonResponse(
        {"error": error, "error_description": description}, status=status
    )
    if status == 401:
        response["WWW-Authenticate"] = 'Basic realm="Kosmos"'
    return _no_store(response)


def _client_credentials(request):
    """``(client_id, client_secret)`` from HTTP Basic or the form body."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Basic "):
        try:
            decoded = base64.b64decode(header[6:], validate=True).decode()
            client_id, _, secret = decoded.partition(":")
            return client_id, secret
        except (ValueError, UnicodeDecodeError):
            return "", ""
    return request.POST.get("client_id", ""), request.POST.get("client_secret", "")


def _authenticated_client(request):
    """The client making a token or revocation request, or a ClientError.
    A confidential client must present its secret; a public one just its
    id."""
    client_id, secret = _client_credentials(request)
    client = resolve_client(client_id)
    if not client.is_public and not client.check_secret(secret):
        raise ClientError("invalid_client", "Client authentication failed.")
    return client


def _with_client(view):
    @wraps(view)
    def wrapper(request):
        try:
            client = _authenticated_client(request)
        except ClientError as exc:
            return _token_error(exc.error, exc.description, status=401)
        return view(request, client)

    return wrapper


def _pkce_matches(verifier, challenge):
    if not (43 <= len(verifier) <= 128):
        return False
    computed = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return secrets.compare_digest(computed, challenge)


def _token_response(connection):
    access, refresh, expires_in = McpToken.issue(connection)
    return _no_store(
        JsonResponse(
            {
                "access_token": access,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": refresh,
            }
        )
    )


@csrf_exempt
@require_http_methods(["POST"])
@_with_client
def token(request, client):
    """Form-encoded, as RFC 6749 says. Two grants: the code from the
    consent screen, and a refresh token."""
    grant_type = request.POST.get("grant_type", "")
    if grant_type == "authorization_code":
        code = McpAuthorizationCode.redeem(request.POST.get("code", ""), client)
        if code is None:
            return _token_error("invalid_grant", "The code is unknown or expired.")
        if request.POST.get("redirect_uri", "") != code.redirect_uri:
            return _token_error("invalid_grant", "redirect_uri does not match.")
        if not _pkce_matches(
            request.POST.get("code_verifier", ""), code.code_challenge
        ):
            return _token_error("invalid_grant", "The PKCE verifier does not match.")
        resource = request.POST.get("resource", "")
        if resource and not _same_resource(request, resource):
            return _token_error("invalid_target", "The resource is not this server.")
        connection = McpConnection.objects.create(user=code.user, client=client)
        return _token_response(connection)
    if grant_type == "refresh_token":
        connection = McpToken.refresh(request.POST.get("refresh_token", ""), client)
        if connection is None:
            return _token_error(
                "invalid_grant", "The refresh token is unknown, expired or revoked."
            )
        resource = request.POST.get("resource", "")
        if resource and not _same_resource(request, resource):
            return _token_error("invalid_target", "The resource is not this server.")
        return _token_response(connection)
    return _token_error(
        "unsupported_grant_type",
        "grant_type must be authorization_code or refresh_token.",
    )


@csrf_exempt
@require_http_methods(["POST"])
@_with_client
def revoke(request, client):
    """RFC 7009. Either token of a connection ends the whole connection.
    An unknown token is a success, as the RFC says."""
    presented = digest(request.POST.get("token", ""))
    row = (
        McpToken.objects.filter(connection__client=client)
        .filter(Q(access_hash=presented) | Q(refresh_hash=presented))
        .select_related("connection")
        .first()
    )
    if row is not None:
        row.connection.delete()
    return _no_store(HttpResponse(status=200))
