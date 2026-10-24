"""Settings > Integrations > QuickBooks Online: what the page offers, and
the connect, callback and disconnect views. Intuit itself is stubbed out
in apps/books/intuit.py's tests; here `intuit.connect` is replaced."""

import pytest
from django.urls import reverse

from apps.books import intuit
from apps.books.models import QuickBooksConnection
from apps.settings.integrations import PENDING_TOAST_KEY
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db

INDEX = "/settings/integrations/"


@pytest.fixture
def books_on(db):
    firm = Firm.objects.first() or Firm.objects.create(name="Firm")
    firm.books_enabled = True
    firm.save()
    return firm


@pytest.fixture
def keys(settings):
    settings.QUICKBOOKS_CLIENT_ID = "client-id"
    settings.QUICKBOOKS_CLIENT_SECRET = "client-secret"
    settings.QUICKBOOKS_ENVIRONMENT = "sandbox"


@pytest.fixture
def no_keys(settings):
    settings.QUICKBOOKS_CLIENT_ID = ""
    settings.QUICKBOOKS_CLIENT_SECRET = ""


@pytest.fixture
def connection(books_on):
    conn = QuickBooksConnection(
        realm_id="4620816365", company_name="Craig Legal", environment="sandbox"
    )
    conn.set_tokens("a", "r")
    conn.save()
    return conn


class TestPage:
    def test_offers_connect_with_keys_and_books_on(self, admin_client, books_on, keys):
        html = admin_client.get(INDEX).content.decode()
        assert "QuickBooks Online" in html
        assert reverse("settings:quickbooks-connect") in html
        assert "(sandbox)" in html

    def test_says_why_without_keys(self, admin_client, books_on, no_keys):
        html = admin_client.get(INDEX).content.decode()
        assert "QuickBooks Online" in html
        assert "QUICKBOOKS_CLIENT_ID" in html
        assert reverse("settings:quickbooks-connect") not in html

    def test_hidden_while_books_is_off(self, admin_client, keys):
        Firm.objects.create(name="Firm", books_enabled=False)
        assert "QuickBooks" not in admin_client.get(INDEX).content.decode()

    def test_hidden_from_staff(self, client, books_on, keys):
        assert "QuickBooks" not in client.get(INDEX).content.decode()

    def test_shows_the_company_when_connected(self, admin_client, connection, keys):
        html = admin_client.get(INDEX).content.decode()
        assert "Craig Legal" in html
        assert "4620816365" in html
        assert "Not synced yet" in html
        assert reverse("settings:quickbooks-disconnect") in html
        assert reverse("settings:quickbooks-connect") not in html


class TestConnect:
    def test_sends_the_admin_to_intuit_with_a_state(self, admin_client, books_on, keys):
        response = admin_client.get(reverse("settings:quickbooks-connect"))
        assert response.status_code == 302
        assert response.url.startswith(intuit.AUTHORIZE_URL)
        state = admin_client.session["quickbooks_state"]
        assert state and f"state={state}" in response.url
        assert (
            "redirect_uri=https%3A%2F%2Ftestserver%2Fsettings%2Fquickbooks%2Fstore"
            in response.url
        )

    def test_without_keys_returns_with_a_toast(self, admin_client, books_on, no_keys):
        response = admin_client.get(reverse("settings:quickbooks-connect"))
        assert response.status_code == 302 and response.url == INDEX
        assert admin_client.session[PENDING_TOAST_KEY]["type"] == "error"

    def test_staff_are_refused(self, client, books_on, keys):
        assert client.get(reverse("settings:quickbooks-connect")).status_code == 403

    def test_not_found_while_books_is_off(self, admin_client, keys):
        Firm.objects.create(name="Firm", books_enabled=False)
        assert (
            admin_client.get(reverse("settings:quickbooks-connect")).status_code == 404
        )


class TestStore:
    def _start(self, client):
        session = client.session
        session["quickbooks_state"] = "s1"
        session.save()

    def test_refuses_a_callback_this_session_did_not_start(
        self, admin_client, books_on, keys
    ):
        response = admin_client.get(
            "/settings/quickbooks/store?code=c&state=x&realmId=1"
        )
        assert response.status_code == 400
        assert not QuickBooksConnection.objects.exists()

    def test_connects_and_says_so(self, admin_client, books_on, keys, monkeypatch):
        calls = []

        def fake_connect(code, realm_id, redirect, user=None):
            calls.append((code, realm_id, redirect, user))
            return QuickBooksConnection(realm_id=realm_id, company_name="Craig Legal")

        monkeypatch.setattr(intuit, "connect", fake_connect)
        self._start(admin_client)

        response = admin_client.get(
            "/settings/quickbooks/store?code=the-code&state=s1&realmId=4620816365"
        )

        assert response.status_code == 302 and response.url == INDEX
        code, realm_id, redirect, user = calls[0]
        assert (code, realm_id) == ("the-code", "4620816365")
        assert redirect == "https://testserver/settings/quickbooks/store"
        assert user.is_admin
        toast = admin_client.session[PENDING_TOAST_KEY]
        assert toast["type"] == "success" and "Craig Legal" in toast["message"]
        # The state is single-use.
        assert "quickbooks_state" not in admin_client.session

    def test_a_cancelled_sign_in_returns_with_an_error(
        self, admin_client, books_on, keys, monkeypatch
    ):
        monkeypatch.setattr(
            intuit, "connect", lambda *a, **k: pytest.fail("not called")
        )
        self._start(admin_client)
        response = admin_client.get(
            "/settings/quickbooks/store?error=access_denied&state=s1"
        )
        assert response.status_code == 302
        assert admin_client.session[PENDING_TOAST_KEY]["type"] == "error"

    def test_a_refused_code_returns_with_the_reason(
        self, admin_client, books_on, keys, monkeypatch
    ):
        def refuse(*args, **kwargs):
            raise intuit.QuickBooksError(
                "Intuit refused the token request: invalid_grant (400)"
            )

        monkeypatch.setattr(intuit, "connect", refuse)
        self._start(admin_client)
        response = admin_client.get(
            "/settings/quickbooks/store?code=c&state=s1&realmId=1"
        )
        assert response.status_code == 302
        assert "invalid_grant" in admin_client.session[PENDING_TOAST_KEY]["message"]

    def test_missing_code_or_company(self, admin_client, books_on, keys):
        self._start(admin_client)
        assert (
            admin_client.get("/settings/quickbooks/store?state=s1").status_code == 400
        )


class TestDisconnect:
    def test_forgets_the_connection(self, admin_client, connection, keys, monkeypatch):
        revoked = []
        monkeypatch.setattr(
            intuit, "revoke", lambda conn: revoked.append(conn.realm_id)
        )
        response = admin_client.post(reverse("settings:quickbooks-disconnect"))
        assert response.status_code == 302
        assert revoked == ["4620816365"]
        assert not QuickBooksConnection.objects.exists()

    def test_get_is_not_allowed(self, admin_client, connection, keys):
        assert (
            admin_client.get(reverse("settings:quickbooks-disconnect")).status_code
            == 405
        )

    def test_staff_are_refused(self, client, connection, keys):
        assert client.post(reverse("settings:quickbooks-disconnect")).status_code == 403
        assert QuickBooksConnection.objects.exists()
