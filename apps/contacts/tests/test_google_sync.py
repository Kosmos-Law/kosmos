"""The cloud button copies a contact to the firm's Google Contacts or removes
the copy. It changes things, so it takes a POST, and it is shown only when a
Google account is connected: without one it did nothing and said nothing.
"""

import json

import pytest
from django.urls import reverse

import apps.contacts.google as google

pytestmark = pytest.mark.django_db


@pytest.fixture
def connected(monkeypatch):
    calls = {"added": [], "deleted": []}
    monkeypatch.setattr(google, "check_credentials", lambda: True)
    monkeypatch.setattr(
        google,
        "add_contact",
        lambda contact: calls["added"].append(contact.id) or "people/c123",
    )
    monkeypatch.setattr(
        google,
        "delete_contact",
        lambda contact: calls["deleted"].append(contact.id) or True,
    )
    return calls


@pytest.fixture
def not_connected(monkeypatch):
    monkeypatch.setattr(google, "check_credentials", lambda: False)


def _url(contact):
    return reverse("contacts:toggle-google-sync", args=[contact.id])


def test_a_link_cannot_toggle_the_google_copy(client, contact, connected):
    response = client.get(_url(contact))

    assert response.status_code == 405
    contact.refresh_from_db()
    assert not contact.google_id
    assert connected["added"] == []


def test_the_button_copies_the_contact_to_google(client, contact, connected):
    response = client.post(_url(contact), HTTP_HX_REQUEST="true")

    assert response.status_code == 204
    assert response.headers["HX-Refresh"] == "true"
    contact.refresh_from_db()
    assert contact.google_id == "people/c123"


def test_the_button_removes_the_google_copy(client, contact, connected):
    contact.google_id = "people/c123"
    contact.save()

    client.post(_url(contact), HTTP_HX_REQUEST="true")

    contact.refresh_from_db()
    assert contact.google_id == ""
    assert connected["deleted"] == [contact.id]


def test_nothing_changes_when_google_is_not_connected(client, contact, not_connected):
    contact.google_id = "people/c123"
    contact.save()

    response = client.post(_url(contact), HTTP_HX_REQUEST="true")

    assert response.status_code == 204
    assert "not connected" in json.loads(response.headers["HX-Toast"])["message"]
    contact.refresh_from_db()
    assert contact.google_id == "people/c123"


def test_the_button_is_shown_only_when_google_is_connected(
    client, contact, monkeypatch
):
    page = reverse("contacts:detail-details", args=[contact.id])

    monkeypatch.setattr(google, "check_credentials", lambda: False)
    assert _url(contact) not in client.get(page).content.decode()

    monkeypatch.setattr(google, "check_credentials", lambda: True)
    body = client.get(page).content.decode()
    assert f'hx-post="{_url(contact)}"' in body
