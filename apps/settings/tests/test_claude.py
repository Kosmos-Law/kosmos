"""Settings > Claude: the connector address, the connected applications and
Disconnect, and the API token buttons that stayed on the page."""

import pytest

from apps.accounts.models import ApiToken, CustomUser
from apps.mcp.models import McpClient, McpConnection

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _request_derived_base_url(settings):
    settings.PUBLIC_BASE_URL = ""


@pytest.fixture
def connection(user):
    claude = McpClient.objects.create(
        client_id="claude", name="Claude", redirect_uris=["https://claude.ai/cb"]
    )
    return McpConnection.objects.create(user=user, client=claude)


def test_page_shows_the_connector_address(client):
    response = client.get("/settings/claude/")
    assert response.status_code == 200
    page = response.content.decode()
    assert "http://testserver/mcp" in page
    assert "Nothing is connected yet." in page


def test_page_lists_connections(client, connection):
    page = client.get("/settings/claude/").content.decode()
    assert "Claude" in page
    assert f"/settings/claude/disconnect/{connection.id}/" in page


def test_disconnect(client, connection):
    response = client.post(f"/settings/claude/disconnect/{connection.id}/")
    assert response.status_code == 302
    assert not McpConnection.objects.exists()


def test_cannot_disconnect_another_users_connection(client, connection):
    other = CustomUser.objects.create(username="other", email="other@example.com")
    connection.user = other
    connection.save()
    response = client.post(f"/settings/claude/disconnect/{connection.id}/")
    assert response.status_code == 404
    assert McpConnection.objects.exists()


def test_token_generate_rotate_revoke(client, user):
    assert client.post("/settings/claude/rotate/").status_code == 302
    first = ApiToken.objects.get(user=user).key
    client.post("/settings/claude/rotate/")
    assert ApiToken.objects.get(user=user).key != first
    client.post("/settings/claude/revoke/")
    assert not ApiToken.objects.filter(user=user).exists()
