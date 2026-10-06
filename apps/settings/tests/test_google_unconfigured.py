"""Settings › Integrations on a server where Google sign-in isn't set up.

Every Google connection runs through one OAuth client file
(GOOGLE_DATA_DIR/google_tokens.json). Without it a Connect button can only
fail, so the page offers none and says why, and the login view refuses
gracefully instead of raising.
"""

import json

import pytest
from django.urls import reverse

from apps.settings.integrations import views as integration_views
from apps.settings.integrations.oauth import google_oauth_configured

pytestmark = pytest.mark.django_db

CLIENT_FILE = {
    "web": {
        "client_id": "abc.apps.googleusercontent.com",
        "client_secret": "secret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


@pytest.fixture
def no_client_file(settings, tmp_path):
    settings.GOOGLE_CLIENT_SECRET_PATH = tmp_path / "google_tokens.json"
    return settings.GOOGLE_CLIENT_SECRET_PATH


@pytest.fixture
def client_file(settings, tmp_path):
    path = tmp_path / "google_tokens.json"
    path.write_text(json.dumps(CLIENT_FILE))
    settings.GOOGLE_CLIENT_SECRET_PATH = path
    return path


def test_no_client_file_is_not_configured(no_client_file):
    assert google_oauth_configured() is False


@pytest.mark.parametrize("content", ["", "not json", "[]", '{"token": "t"}'])
def test_unusable_client_file_is_not_configured(no_client_file, content):
    no_client_file.write_text(content)
    assert google_oauth_configured() is False


def test_client_file_is_configured(client_file):
    assert google_oauth_configured() is True


def test_installed_client_file_is_configured(no_client_file):
    no_client_file.write_text(json.dumps({"installed": CLIENT_FILE["web"]}))
    assert google_oauth_configured() is True


def test_admin_sees_no_connect_buttons_and_the_reason(admin_client, no_client_file):
    body = admin_client.get(reverse("settings:integrations-index")).content.decode()

    assert ">Connect</a>" not in body
    assert "Google sign-in isn't set up on this server yet" in body
    assert "docs/admin/integrations/google.md" in body


def test_user_is_told_to_ask_an_administrator(client, no_client_file):
    body = client.get(reverse("settings:integrations-index")).content.decode()

    assert ">Connect</a>" not in body
    assert "Ask an administrator" in body


def test_connect_buttons_show_once_configured(admin_client, client_file):
    body = admin_client.get(reverse("settings:integrations-index")).content.decode()

    for app in ("contacts", "calendar", "drive", "email"):
        assert reverse("settings:google-login", args=[app]) in body
    assert "Google sign-in isn't set up" not in body


@pytest.mark.parametrize("app", ["contacts", "calendar", "drive"])
def test_login_without_client_file_redirects_with_a_toast(
    admin_client, no_client_file, app
):
    response = admin_client.get(reverse("settings:google-login", args=[app]))

    assert response.status_code == 302
    assert response["Location"] == reverse("settings:integrations-index")

    page = admin_client.get(response["Location"]).content.decode()
    assert "integrations-pending-toast" in page
    assert "isn't set up on this server" in page
    # Shown once: the next load is clean.
    again = admin_client.get(response["Location"]).content.decode()
    assert "integrations-pending-toast" not in again


def test_user_gmail_login_without_client_file_redirects(client, no_client_file):
    response = client.get(reverse("settings:google-login", args=["email"]))

    assert response.status_code == 302
    assert response["Location"] == reverse("settings:integrations-index")


def test_login_with_client_file_goes_to_google(admin_client, client_file, monkeypatch):
    monkeypatch.setattr(integration_views, "GOOGLE_TOKEN_PATH", client_file)

    response = admin_client.get(reverse("settings:google-login", args=["calendar"]))

    assert response.status_code == 302
    assert response["Location"].startswith("https://accounts.google.com/")
