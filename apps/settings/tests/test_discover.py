"""Settings > Integrations, Kosmos Discover: the connection Discover made
by signing in (apps/mcp, the matters API's tokens) is listed and ended
here, not under Settings > Claude."""

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.mcp.models import RESOURCE_MATTERS, McpClient, McpConnection, McpToken

pytestmark = pytest.mark.django_db


def connect(user):
    """A Discover connection as ``user``; returns it and an API client
    holding its access token."""
    discover, _ = McpClient.objects.get_or_create(
        client_id="discover",
        defaults={
            "name": "Kosmos Discover",
            "client_uri": "https://discover.example.com",
            "redirect_uris": ["https://discover.example.com/kosmos/callback/"],
        },
    )
    connection = McpConnection.objects.create(
        user=user, client=discover, resource=RESOURCE_MATTERS
    )
    access, _refresh, _expires = McpToken.issue(connection)
    return connection, Client(HTTP_AUTHORIZATION=f"Bearer {access}")


def signed_in(**fields):
    # Seen the Dash today, or the first page would be a redirect to it.
    user = CustomUser.objects.create(
        user_rate=100, last_dash_check=timezone.localdate(), **fields
    )
    client = Client()
    client.force_login(user)
    return user, client


def test_it_is_listed_under_integrations_not_claude(client, user):
    connection, _api = connect(user)
    page = client.get("/settings/integrations/").content.decode()
    assert "Kosmos Discover" in page and "<td>discover.example.com</td>" in page
    assert f"/settings/integrations/discover/{connection.id}/disconnect/" in page
    claude = client.get("/settings/claude/").content.decode()
    assert "Nothing is connected yet." in claude and "Kosmos Discover" not in claude


def test_disconnect_ends_its_access(client, user):
    connection, api = connect(user)
    assert api.get("/matters/api/").status_code == 200
    response = client.post(
        f"/settings/integrations/discover/{connection.id}/disconnect/"
    )
    assert response.status_code == 302
    assert not McpConnection.objects.exists()
    assert api.get("/matters/api/").status_code == 401


def test_claude_settings_cannot_end_it(client, user):
    # That page's Disconnect is for Claude's connections.
    connection, _api = connect(user)
    response = client.post(f"/settings/claude/disconnect/{connection.id}/")
    assert response.status_code == 404
    assert McpConnection.objects.filter(pk=connection.pk).exists()


def test_an_administrator_sees_and_ends_anyones(user):
    connection, api = connect(user)
    _admin, admin = signed_in(
        username="discover-admin", email="discover-admin@example.com", role="ADMIN"
    )
    page = admin.get("/settings/integrations/").content.decode()
    assert f"/settings/integrations/discover/{connection.id}/disconnect/" in page
    admin.post(f"/settings/integrations/discover/{connection.id}/disconnect/")
    assert api.get("/matters/api/").status_code == 401


def test_another_user_neither_sees_nor_ends_it(user):
    connection, api = connect(user)
    _other, other = signed_in(
        username="discover-other", email="discover-other@example.com"
    )
    page = other.get("/settings/integrations/").content.decode()
    # No section at all for someone with nothing connected.
    assert "Kosmos Discover" not in page
    response = other.post(
        f"/settings/integrations/discover/{connection.id}/disconnect/"
    )
    assert response.status_code == 404
    assert api.get("/matters/api/").status_code == 200


def test_an_administrator_is_told_how_it_is_connected(user):
    _admin, admin = signed_in(
        username="discover-admin", email="discover-admin@example.com", role="ADMIN"
    )
    page = admin.get("/settings/integrations/").content.decode()
    assert "made from Discover" in " ".join(page.split())
    assert "Nothing is connected yet." in page
