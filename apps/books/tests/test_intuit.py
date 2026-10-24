"""The QuickBooks Online connection (apps/books/intuit.py): the OAuth
exchange, the refresh, the API client and disconnecting, against a stub of
`requests`. Nothing here reaches Intuit."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.books import intuit
from apps.books.models import QuickBooksConnection

pytestmark = pytest.mark.django_db

TOKENS = {
    "access_token": "access-1",
    "refresh_token": "refresh-1",
    "expires_in": 3600,
    "x_refresh_token_expires_in": 8726400,
    "token_type": "bearer",
}


class FakeResponse:
    def __init__(self, status_code=200, body=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeRequests:
    """`requests` with queued answers. Each call pops the next response
    for its verb and records what was sent."""

    RequestException = intuit.requests.RequestException

    def __init__(self):
        self.posts = []
        self.gets = []
        self.post_queue = []
        self.get_queue = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.post_queue.pop(0) if self.post_queue else FakeResponse(200, {})

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return self.get_queue.pop(0) if self.get_queue else FakeResponse(200, {})


@pytest.fixture
def keys(settings):
    settings.QUICKBOOKS_CLIENT_ID = "client-id"
    settings.QUICKBOOKS_CLIENT_SECRET = "client-secret"
    settings.QUICKBOOKS_ENVIRONMENT = "sandbox"


@pytest.fixture
def fake(monkeypatch):
    fake = FakeRequests()
    monkeypatch.setattr(intuit, "requests", fake)
    # The discovery document is fetched once a day; these tests are about
    # what follows it, so it is already known.
    monkeypatch.setattr(
        intuit,
        "_discovered",
        {
            env: (timezone.now(), dict(intuit.DEFAULT_ENDPOINTS))
            for env in intuit.DISCOVERY_URLS
        },
    )
    return fake


@pytest.fixture
def undiscovered(monkeypatch):
    monkeypatch.setattr(intuit, "_discovered", {})


DISCOVERY = {
    "issuer": "https://oauth.platform.intuit.com/op/v1",
    "authorization_endpoint": "https://appcenter.intuit.com/connect/oauth2",
    "token_endpoint": "https://oauth.platform.intuit.com/oauth2/v2/tokens/bearer",
    "revocation_endpoint": "https://developer.api.intuit.com/v2/oauth2/tokens/revoke",
}


class TestDiscovery:
    def test_reads_the_endpoints_for_the_environment(self, keys, fake, undiscovered):
        fake.get_queue = [FakeResponse(200, DISCOVERY)]

        found = intuit.endpoints()

        assert fake.gets[0][0] == intuit.DISCOVERY_URLS["sandbox"]
        assert (
            found["token"]
            == "https://oauth.platform.intuit.com/oauth2/v2/tokens/bearer"
        )
        assert found["authorize"] == intuit.AUTHORIZE_URL
        assert found["revoke"] == intuit.REVOKE_URL

    def test_fetched_once_a_day(self, keys, fake, undiscovered):
        fake.get_queue = [FakeResponse(200, DISCOVERY)]
        intuit.endpoints()
        intuit.endpoints()
        intuit.endpoints("production")
        assert [url for url, _ in fake.gets] == [
            intuit.DISCOVERY_URLS["sandbox"],
            intuit.DISCOVERY_URLS["production"],
        ]

    def test_falls_back_when_the_document_cannot_be_read(
        self, keys, fake, undiscovered
    ):
        fake.get_queue = [FakeResponse(503, None)]
        assert intuit.endpoints() == intuit.DEFAULT_ENDPOINTS
        fake.get_queue = [FakeResponse(200, {"token_endpoint": 7})]
        intuit._discovered.clear()
        assert intuit.endpoints() == intuit.DEFAULT_ENDPOINTS

    def test_the_token_request_uses_the_discovered_endpoint(
        self, keys, fake, undiscovered
    ):
        fake.get_queue = [FakeResponse(200, DISCOVERY)]
        fake.post_queue = [FakeResponse(200, TOKENS)]
        intuit.connect("c", "1", "https://k/store")
        assert fake.posts[0][0] == DISCOVERY["token_endpoint"]

    def test_authorize_url_uses_the_discovered_endpoint(self, keys, fake, undiscovered):
        fake.get_queue = [
            FakeResponse(
                200, {**DISCOVERY, "authorization_endpoint": "https://x.intuit.com/a"}
            )
        ]
        assert intuit.authorize_url("https://k/store", "s").startswith(
            "https://x.intuit.com/a?"
        )


@pytest.fixture
def connected(keys):
    conn = QuickBooksConnection(
        realm_id="123", company_name="Sample", environment="sandbox"
    )
    conn.set_tokens("access-0", "refresh-0")
    conn.access_expires_at = timezone.now() + timedelta(hours=1)
    conn.refresh_expires_at = timezone.now() + timedelta(days=100)
    conn.save()
    return conn


class TestConfiguration:
    def test_needs_both_keys(self, settings):
        settings.QUICKBOOKS_CLIENT_ID = "id"
        settings.QUICKBOOKS_CLIENT_SECRET = ""
        assert not intuit.configured()
        settings.QUICKBOOKS_CLIENT_SECRET = "secret"
        assert intuit.configured()

    def test_environment_is_sandbox_or_production(self, settings):
        settings.QUICKBOOKS_ENVIRONMENT = "Sandbox "
        assert intuit.environment() == "sandbox"
        settings.QUICKBOOKS_ENVIRONMENT = "anything else"
        assert intuit.environment() == "production"

    def test_authorize_url(self, keys):
        url = intuit.authorize_url("https://k.example/settings/quickbooks/store", "s1")
        assert url.startswith(intuit.AUTHORIZE_URL + "?")
        assert "client_id=client-id" in url
        assert "scope=com.intuit.quickbooks.accounting" in url
        assert (
            "redirect_uri=https%3A%2F%2Fk.example%2Fsettings%2Fquickbooks%2Fstore"
            in url
        )
        assert "state=s1" in url
        assert "response_type=code" in url


class TestConnect:
    def test_trades_the_code_and_records_the_company(self, keys, fake):
        fake.post_queue = [FakeResponse(200, TOKENS)]
        fake.get_queue = [FakeResponse(200, {"CompanyInfo": {"CompanyName": "Craig"}})]

        conn = intuit.connect("the-code", "4620816365", "https://k/store")

        url, kwargs = fake.posts[0]
        assert url == intuit.TOKEN_URL
        assert kwargs["auth"] == ("client-id", "client-secret")
        assert kwargs["data"] == {
            "grant_type": "authorization_code",
            "code": "the-code",
            "redirect_uri": "https://k/store",
        }
        assert conn.realm_id == "4620816365"
        assert conn.environment == "sandbox"
        assert conn.company_name == "Craig"
        assert conn.access == "access-1"
        assert conn.refresh == "refresh-1"
        # The company call went to the sandbox host with the new token.
        url, kwargs = fake.gets[0]
        assert url.startswith(
            "https://sandbox-quickbooks.api.intuit.com/v3/company/4620816365/companyinfo/"
        )
        assert kwargs["headers"]["Authorization"] == "Bearer access-1"
        assert kwargs["params"]["minorversion"] == intuit.MINOR_VERSION

    def test_tokens_are_sealed_at_rest(self, keys, fake):
        fake.post_queue = [FakeResponse(200, TOKENS)]
        intuit.connect("c", "1", "https://k/store")
        row = QuickBooksConnection.objects.get()
        assert "access-1" not in row.access_token
        assert "refresh-1" not in row.refresh_token
        assert row.access == "access-1"

    def test_replaces_an_earlier_connection(self, connected, fake):
        fake.post_queue = [FakeResponse(200, TOKENS)]
        intuit.connect("c", "999", "https://k/store")
        assert list(
            QuickBooksConnection.objects.values_list("realm_id", flat=True)
        ) == ["999"]

    def test_a_refused_code_raises(self, keys, fake):
        fake.post_queue = [FakeResponse(400, {"error": "invalid_grant"})]
        with pytest.raises(intuit.QuickBooksError, match="invalid_grant"):
            intuit.connect("bad", "1", "https://k/store")
        assert not QuickBooksConnection.objects.exists()

    def test_company_info_failing_keeps_the_connection(self, keys, fake):
        fake.post_queue = [FakeResponse(200, TOKENS)]
        fake.get_queue = [FakeResponse(500, None)]
        conn = intuit.connect("c", "1", "https://k/store")
        assert conn.pk and conn.company_name == ""


class TestRefresh:
    def test_posts_the_refresh_token_and_saves_the_new_pair(self, connected, fake):
        connected.access_expires_at = timezone.now()
        connected.save()
        fake.post_queue = [FakeResponse(200, {**TOKENS, "refresh_token": "refresh-2"})]

        fresh = intuit.refresh(connected)

        _, kwargs = fake.posts[0]
        assert kwargs["data"] == {
            "grant_type": "refresh_token",
            "refresh_token": "refresh-0",
        }
        assert fresh.access == "access-1"
        assert fresh.refresh == "refresh-2"
        assert fresh.access_is_fresh()
        assert QuickBooksConnection.objects.get().refresh == "refresh-2"

    def test_a_fresh_token_is_not_refreshed(self, connected, fake):
        intuit.refresh(connected)
        assert fake.posts == []

    def test_invalid_grant_means_the_connection_is_lost(self, connected, fake):
        connected.access_expires_at = timezone.now()
        connected.save()
        fake.post_queue = [FakeResponse(400, {"error": "invalid_grant"})]
        with pytest.raises(intuit.ConnectionLost):
            intuit.refresh(connected)

    def test_unreadable_tokens_mean_the_connection_is_lost(self, connected, fake):
        connected.refresh_token = "not-sealed"
        connected.access_expires_at = timezone.now()
        connected.save()
        with pytest.raises(intuit.ConnectionLost):
            intuit.refresh(connected)


class TestClient:
    def test_no_connection(self):
        with pytest.raises(intuit.NotConnected):
            intuit.Client(None)

    def test_refreshes_a_stale_token_first(self, connected, fake):
        connected.access_expires_at = timezone.now() + timedelta(minutes=1)
        connected.save()
        fake.post_queue = [FakeResponse(200, TOKENS)]
        fake.get_queue = [FakeResponse(200, {"QueryResponse": {"Account": []}})]

        assert intuit.Client(connected).query("select * from Account") == {
            "Account": []
        }

        assert len(fake.posts) == 1
        assert fake.gets[0][1]["headers"]["Authorization"] == "Bearer access-1"
        assert fake.gets[0][1]["params"]["query"] == "select * from Account"

    def test_retries_once_after_a_401(self, connected, fake):
        fake.get_queue = [FakeResponse(401, None), FakeResponse(200, {"Header": {}})]
        fake.post_queue = [FakeResponse(200, TOKENS)]

        assert intuit.Client(connected).report(
            "TrialBalance", date_macro="This Fiscal Year"
        ) == {"Header": {}}

        assert len(fake.gets) == 2
        assert fake.gets[0][1]["headers"]["Authorization"] == "Bearer access-0"
        assert fake.gets[1][1]["headers"]["Authorization"] == "Bearer access-1"
        assert fake.gets[1][0].endswith("/reports/TrialBalance")
        assert fake.gets[1][1]["params"]["date_macro"] == "This Fiscal Year"

    def test_other_errors_raise(self, connected, fake):
        fake.get_queue = [FakeResponse(500, {"Fault": {}})]
        with pytest.raises(intuit.QuickBooksError, match="HTTP 500"):
            intuit.Client(connected).company_info()

    def test_errors_carry_intuits_transaction_id_and_message(self, connected, fake):
        fake.get_queue = [
            FakeResponse(
                400,
                {"Fault": {"Error": [{"Message": "Invalid query", "code": "4000"}]}},
                headers={"intuit_tid": "1-2-3-abc"},
            )
        ]
        with pytest.raises(intuit.QuickBooksError) as caught:
            intuit.Client(connected).query("select nonsense")
        assert "Invalid query (400), intuit_tid 1-2-3-abc" in str(caught.value)

    def test_the_production_host(self, connected, fake, settings):
        settings.QUICKBOOKS_ENVIRONMENT = "production"
        connected.environment = "production"
        connected.save()
        intuit.Client(connected).company_info()
        assert fake.gets[0][0].startswith("https://quickbooks.api.intuit.com/")

    def test_a_connection_from_the_other_environment_is_refused(self, connected, fake):
        """A dev server loaded with production's database: sandbox keys,
        a production connection. Nothing is sent to Intuit."""
        connected.environment = "production"
        connected.access_expires_at = timezone.now()
        connected.save()
        with pytest.raises(intuit.WrongEnvironment, match="production QuickBooks"):
            intuit.Client(connected)
        assert fake.posts == [] and fake.gets == []


class TestDisconnect:
    def test_revokes_and_forgets(self, connected, fake):
        assert intuit.disconnect() is True
        url, kwargs = fake.posts[0]
        assert url == intuit.REVOKE_URL
        assert kwargs["json"] == {"token": "refresh-0"}
        assert not QuickBooksConnection.objects.exists()

    def test_a_failed_revoke_still_forgets(self, connected, fake):
        fake.post_queue = [FakeResponse(400, {"error": "invalid_token"})]
        assert intuit.disconnect() is True
        assert not QuickBooksConnection.objects.exists()

    def test_nothing_to_disconnect(self, keys, fake):
        assert intuit.disconnect() is False
        assert fake.posts == []
