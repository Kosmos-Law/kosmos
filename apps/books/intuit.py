"""The QuickBooks Online connection: Intuit's OAuth 2.0 and the API calls
the mirror makes with it.

The firm has one connection (`QuickBooksConnection`, one row). An
administrator starts it under Settings > Integrations: `authorize_url`
sends them to Intuit, Intuit sends them back to /settings/quickbooks/store
with a code and the company's realm id, and `connect` trades the code for
tokens and asks the company its name. From then on `Client` makes the
calls, refreshing the access token when it is about to expire and once
more if the API refuses it anyway. Every refresh may issue a new refresh
token, and Intuit revokes the whole connection if an old one is reused,
so a refresh locks the row and the new tokens are saved before anything
else uses them.

The sandbox and production companies live on different hosts and answer
to different keys (development and production keys on the developer
portal). The connection records which it was made against and the client
uses that host; config/.env's QUICKBOOKS_ENVIRONMENT decides only new
connections.
"""

import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.books.models import QuickBooksConnection

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
SCOPE = "com.intuit.quickbooks.accounting"
API_HOSTS = {
    QuickBooksConnection.SANDBOX: "https://sandbox-quickbooks.api.intuit.com",
    QuickBooksConnection.PRODUCTION: "https://quickbooks.api.intuit.com",
}
# The API's minor version: the shape of the responses. Intuit retires old
# ones; 75 is the floor it set in 2025.
MINOR_VERSION = 75
TIMEOUT = 30
# Refresh an access token with this long still to run, so a call that
# starts now does not meet an expired token.
ACCESS_MARGIN = timedelta(minutes=5)


class QuickBooksError(Exception):
    """Intuit refused or could not be reached. The message is for the
    page or the sync log."""


class NotConnected(QuickBooksError):
    """There is no connection to make the call with."""


class ConnectionLost(QuickBooksError):
    """Intuit no longer honours the refresh token (it expired, was
    revoked, or reused): an administrator must connect again."""


# ------------------------------------------------------------- configuration


def configured():
    """True when config/.env holds the app's client id and secret."""
    return bool(settings.QUICKBOOKS_CLIENT_ID and settings.QUICKBOOKS_CLIENT_SECRET)


def environment():
    env = (settings.QUICKBOOKS_ENVIRONMENT or "").strip().lower()
    return (
        QuickBooksConnection.SANDBOX
        if env == QuickBooksConnection.SANDBOX
        else QuickBooksConnection.PRODUCTION
    )


def redirect_uri(request):
    """Where Intuit sends the administrator back: registered on the
    developer portal character for character, so always https and never
    a trailing slash, like the Google callback."""
    return f"https://{request.get_host()}/settings/quickbooks/store"


def new_state():
    return secrets.token_urlsafe(32)


def authorize_url(redirect, state):
    query = urlencode(
        {
            "client_id": settings.QUICKBOOKS_CLIENT_ID,
            "scope": SCOPE,
            "redirect_uri": redirect,
            "response_type": "code",
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def connection():
    """The firm's connection, or None."""
    return QuickBooksConnection.objects.order_by("id").first()


# --------------------------------------------------------------------- tokens


def _auth():
    return (settings.QUICKBOOKS_CLIENT_ID, settings.QUICKBOOKS_CLIENT_SECRET)


def _describe(response):
    try:
        body = response.json()
    except ValueError:
        body = {}
    if isinstance(body, dict):
        reason = body.get("error_description") or body.get("error")
        if reason:
            return f"{reason} ({response.status_code})"
    return f"HTTP {response.status_code}"


def _token_request(data):
    try:
        response = requests.post(
            TOKEN_URL,
            data=data,
            auth=_auth(),
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise QuickBooksError(f"Intuit could not be reached: {exc}") from exc
    if response.status_code != 200:
        raise QuickBooksError(
            f"Intuit refused the token request: {_describe(response)}"
        )
    return response.json()


def _apply_tokens(conn, tokens):
    now = timezone.now()
    conn.set_tokens(tokens["access_token"], tokens["refresh_token"])
    conn.access_expires_at = now + timedelta(
        seconds=int(tokens.get("expires_in", 3600))
    )
    conn.refresh_expires_at = now + timedelta(
        seconds=int(tokens.get("x_refresh_token_expires_in", 100 * 24 * 3600))
    )


def connect(code, realm_id, redirect, user=None):
    """Trade the code Intuit sent back for tokens, keep them as the firm's
    connection (replacing any earlier one), and record the company's
    name."""
    tokens = _token_request(
        {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect}
    )
    with transaction.atomic():
        QuickBooksConnection.objects.all().delete()
        conn = QuickBooksConnection(
            realm_id=str(realm_id),
            environment=environment(),
            connected_by=user,
            connected_at=timezone.now(),
        )
        _apply_tokens(conn, tokens)
        conn.save()
    try:
        info = Client(conn).company_info()
        conn.company_name = info.get("CompanyName", "")[:255]
        conn.save(update_fields=["company_name"])
    except QuickBooksError as exc:
        # The tokens are good (Intuit just issued them); the name is a
        # nicety the page can live without. Say so in the log.
        logger.warning("QuickBooks connected but the company info failed: %s", exc)
    return conn


def refresh(conn, refused=False):
    """Fresh tokens for ``conn``, saved. Locks the row so two workers do
    not both refresh, which would hand Intuit an already-used refresh token
    and lose the connection. ``refused`` says the API just rejected
    ``conn``'s access token although it looked fresh. Returns the
    connection re-read."""
    with transaction.atomic():
        locked = QuickBooksConnection.objects.select_for_update().get(pk=conn.pk)
        if refused:
            if locked.access != conn.access:
                # Someone refreshed while we waited for the lock.
                return locked
        elif locked.access_is_fresh(ACCESS_MARGIN):
            return locked
        token = locked.refresh
        if not token:
            raise ConnectionLost(
                "The QuickBooks sign-in cannot be read; connect QuickBooks again."
            )
        try:
            tokens = _token_request(
                {"grant_type": "refresh_token", "refresh_token": token}
            )
        except QuickBooksError as exc:
            if "invalid_grant" in str(exc):
                raise ConnectionLost(
                    "QuickBooks no longer accepts this sign-in; connect it again."
                ) from exc
            raise
        _apply_tokens(locked, tokens)
        locked.save(
            update_fields=[
                "access_token",
                "refresh_token",
                "access_expires_at",
                "refresh_expires_at",
            ]
        )
        return locked


def revoke(conn):
    """Tell Intuit the connection is over. A failure is logged, not
    raised: the row goes either way, and an unrevoked refresh token dies
    on its own."""
    token = conn.refresh or conn.access
    if not token:
        return
    try:
        response = requests.post(
            REVOKE_URL,
            json={"token": token},
            auth=_auth(),
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if response.status_code != 200:
            logger.warning("QuickBooks revoke answered %s", _describe(response))
    except requests.RequestException as exc:
        logger.warning("QuickBooks revoke failed: %s", exc)


def disconnect():
    """Revoke and forget the firm's connection, if there is one."""
    conn = connection()
    if conn is None:
        return False
    revoke(conn)
    conn.delete()
    return True


# ------------------------------------------------------------------- the API


class Client:
    """Calls against one company. ``get`` returns the parsed JSON and
    raises QuickBooksError on anything else."""

    def __init__(self, conn):
        if conn is None:
            raise NotConnected("QuickBooks is not connected.")
        self.conn = conn
        self.host = API_HOSTS[conn.environment]

    def _url(self, path):
        return f"{self.host}/v3/company/{self.conn.realm_id}/{path}"

    def _ensure_fresh(self):
        if not self.conn.access_is_fresh(ACCESS_MARGIN):
            self.conn = refresh(self.conn)

    def _send(self, path, params):
        query = {"minorversion": MINOR_VERSION, **(params or {})}
        try:
            return requests.get(
                self._url(path),
                params=query,
                headers={
                    "Authorization": f"Bearer {self.conn.access}",
                    "Accept": "application/json",
                },
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise QuickBooksError(f"QuickBooks could not be reached: {exc}") from exc

    def get(self, path, params=None):
        self._ensure_fresh()
        response = self._send(path, params)
        if response.status_code == 401:
            # The token was refused although it looked fresh: refresh once
            # and try again before giving up.
            self.conn = refresh(self.conn, refused=True)
            response = self._send(path, params)
        if response.status_code != 200:
            raise QuickBooksError(
                f"QuickBooks answered {_describe(response)} for {path}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise QuickBooksError(f"QuickBooks sent no JSON for {path}") from exc

    def company_info(self):
        body = self.get(f"companyinfo/{self.conn.realm_id}")
        return body.get("CompanyInfo", {})

    def query(self, statement):
        """A QuickBooks query (its SQL-like language); the QueryResponse."""
        return self.get("query", {"query": statement}).get("QueryResponse", {})

    def report(self, name, **params):
        """One of the standard reports (AccountList, GeneralLedger,
        TrialBalance, ...) as Intuit's column/row JSON."""
        return self.get(f"reports/{name}", params)
