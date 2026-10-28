"""Google Contacts is per user: each user connects their own Google
account and the cloud button copies a contact to it, or removes their copy.
Editing a contact replaces every user's copy; deleting it removes them.
"""

import json

import pytest
from django.urls import reverse

import apps.contacts.google as google
from apps.accounts.models import CustomUser
from apps.contacts.models import GoogleContactCopy

pytestmark = pytest.mark.django_db

TOKEN = json.dumps({"token": "t", "refresh_token": "r"})


class FakePeople:
    """The People API, as much of it as Kosmos calls."""

    def __init__(self, owner, fail=False):
        self.owner = owner
        self.fail = fail
        self.created = []
        self.deleted = []
        self._call = None

    def people(self):
        return self

    def createContact(self, body):
        self._call = ("create", body)
        return self

    def deleteContact(self, resourceName):
        self._call = ("delete", resourceName)
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError("Google is down")
        kind, value = self._call
        if kind == "create":
            self.created.append(value)
            return {"resourceName": f"people/{self.owner}{len(self.created)}"}
        self.deleted.append(value)
        return {}


def _connect(user):
    """Connect the user, saving only the token: a whole save would undo the
    client fixture's visit to the Dash and every request would redirect."""
    user.google_contacts_credentials = TOKEN
    user.save(update_fields=["google_contacts_credentials"])


@pytest.fixture
def google_accounts(monkeypatch):
    """Each connected user's fake account, by username."""
    accounts = {}

    def build_service(user):
        if not google.is_connected(user):
            return None
        return accounts.setdefault(user.username, FakePeople(user.username))

    monkeypatch.setattr(google, "build_service", build_service)
    return accounts


@pytest.fixture
def connected(user, google_accounts):
    _connect(user)
    return google_accounts


@pytest.fixture
def colleague():
    return CustomUser.objects.create(
        username="Rosa", email="rosa@example.com", google_contacts_credentials=TOKEN
    )


def _url(contact):
    return reverse("contacts:toggle-google-sync", args=[contact.id])


def _page(client, contact):
    return client.get(reverse("contacts:detail-details", args=[contact.id]))


# ── The button ───────────────────────────────────────────────────────────


def test_a_link_cannot_toggle_the_google_copy(client, contact, connected):
    response = client.get(_url(contact))

    assert response.status_code == 405
    assert not GoogleContactCopy.objects.exists()


def test_the_button_copies_the_contact_to_my_google(client, user, contact, connected):
    response = client.post(_url(contact), HTTP_HX_REQUEST="true")

    assert response.status_code == 204
    assert response.headers["HX-Refresh"] == "true"
    copy = GoogleContactCopy.objects.get()
    assert (copy.user, copy.contact, copy.resource_name) == (
        user,
        contact,
        "people/Ollie1",
    )
    assert connected["Ollie"].created[0]["names"] == [
        {"unstructuredName": contact.name}
    ]


def test_the_button_removes_only_my_copy(client, user, contact, connected, colleague):
    GoogleContactCopy.objects.create(user=user, contact=contact, resource_name="c1")
    GoogleContactCopy.objects.create(
        user=colleague, contact=contact, resource_name="c2"
    )

    client.post(_url(contact), HTTP_HX_REQUEST="true")

    assert connected["Ollie"].deleted == ["people/c1"]
    assert list(GoogleContactCopy.objects.values_list("user", flat=True)) == [
        colleague.id
    ]


def test_nothing_changes_when_i_have_not_connected(client, contact, google_accounts):
    response = client.post(_url(contact), HTTP_HX_REQUEST="true")

    assert response.status_code == 204
    assert "not connected" in json.loads(response.headers["HX-Toast"])["message"]
    assert not GoogleContactCopy.objects.exists()


def test_a_failed_copy_says_so_and_records_nothing(client, user, contact, monkeypatch):
    _connect(user)
    monkeypatch.setattr(google, "build_service", lambda u: FakePeople("x", fail=True))

    response = client.post(_url(contact), HTTP_HX_REQUEST="true")

    assert (
        "Couldn't reach Google" in json.loads(response.headers["HX-Toast"])["message"]
    )
    assert not GoogleContactCopy.objects.exists()


def test_the_button_follows_my_own_connection_and_copy(
    client, user, contact, google_accounts, colleague
):
    # A colleague's connection and copy do not show the button to me
    GoogleContactCopy.objects.create(
        user=colleague, contact=contact, resource_name="c2"
    )
    assert _url(contact) not in _page(client, contact).content.decode()

    _connect(user)
    body = _page(client, contact).content.decode()
    assert f'hx-post="{_url(contact)}"' in body
    assert "Copy to your Google Contacts" in body

    GoogleContactCopy.objects.create(user=user, contact=contact, resource_name="c1")
    assert "Remove from your Google Contacts" in _page(client, contact).content.decode()


# ── Editing and deleting ─────────────────────────────────────────────────


def test_editing_replaces_every_reachable_copy(contact, connected, user, colleague):
    mine = GoogleContactCopy.objects.create(
        user=user, contact=contact, resource_name="people/old1"
    )
    theirs = GoogleContactCopy.objects.create(
        user=colleague, contact=contact, resource_name="people/old2"
    )
    unheld = GoogleContactCopy.objects.create(
        user=None, contact=contact, resource_name="people/firm"
    )

    google.refresh_copies(contact)

    assert connected["Ollie"].deleted == ["people/old1"]
    assert connected["Rosa"].deleted == ["people/old2"]
    mine.refresh_from_db()
    theirs.refresh_from_db()
    unheld.refresh_from_db()
    assert mine.resource_name == "people/Ollie1"
    assert theirs.resource_name == "people/Rosa1"
    assert unheld.resource_name == "people/firm"


def _delete(client, contact):
    return client.delete(reverse("contacts:delete", args=[contact.id]))


def test_deleting_removes_every_copy(client, contact, connected, user, colleague):
    GoogleContactCopy.objects.create(user=user, contact=contact, resource_name="c1")
    GoogleContactCopy.objects.create(
        user=colleague, contact=contact, resource_name="c2"
    )

    response = _delete(client, contact)

    assert response.headers["HX-Redirect"] == reverse("contacts:index")
    assert connected["Ollie"].deleted == ["people/c1"]
    assert connected["Rosa"].deleted == ["people/c2"]
    assert not GoogleContactCopy.objects.exists()
    assert "contacts-pending-toast" not in client.get("/contacts/").content.decode()


def test_deleting_warns_about_copies_it_cannot_reach(
    client, contact, user, google_accounts
):
    # Not connected any more, and one left from the firm account
    GoogleContactCopy.objects.create(user=user, contact=contact, resource_name="c1")
    GoogleContactCopy.objects.create(user=None, contact=contact, resource_name="c2")

    response = _delete(client, contact)

    page = client.get(response.headers["HX-Redirect"]).content.decode()
    assert "2 copies in Google" in page
    assert "contacts-pending-toast" not in client.get("/contacts/").content.decode()


def test_deleting_a_contact_with_no_copies_says_nothing(
    client, contact, google_accounts
):
    response = _delete(client, contact)

    page = client.get(response.headers["HX-Redirect"]).content.decode()
    assert "contacts-pending-toast" not in page


# ── Connecting and adopting ──────────────────────────────────────────────


def test_disconnecting_forgets_my_token_and_my_copies(client, user, contact, colleague):
    _connect(user)
    GoogleContactCopy.objects.create(user=user, contact=contact, resource_name="c1")
    GoogleContactCopy.objects.create(
        user=colleague, contact=contact, resource_name="c2"
    )

    client.post(reverse("settings:google-logout", args=["contacts"]))

    user.refresh_from_db()
    assert not google.is_connected(user)
    assert list(GoogleContactCopy.objects.values_list("user", flat=True)) == [
        colleague.id
    ]


def test_adopting_gives_the_firm_accounts_token_and_copies_to_one_user(
    user, contact, settings, tmp_path, monkeypatch
):
    from django.core.management import call_command

    from apps.contacts.management.commands import adopt_google_contacts

    legacy = tmp_path / "contact_tokens.json"
    legacy.write_text(TOKEN)
    monkeypatch.setattr(adopt_google_contacts, "LEGACY_TOKEN_PATH", legacy)
    GoogleContactCopy.objects.create(user=None, contact=contact, resource_name="c1")

    call_command("adopt_google_contacts", user.username)

    user.refresh_from_db()
    assert user.google_contacts_credentials == TOKEN
    assert not legacy.exists()
    assert GoogleContactCopy.objects.get().user == user
