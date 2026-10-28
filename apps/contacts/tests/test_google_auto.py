"""Automatic Google Contacts: a user may have Kosmos copy, on its own, the
client of each Open matter they can see, or everyone in its Client group.
The copies it added go again once their contact no longer qualifies;
copies made with the button are never touched by it."""

import json

import pytest
from django.urls import reverse

import apps.contacts.google as google
from apps.accounts.models import CustomUser
from apps.contacts.models import Contact, GoogleContactCopy, GoogleContactsSetting
from apps.matters.models import Group, Matter, Relationship, Role

from .test_google_sync import TOKEN, FakePeople, _connect

pytestmark = pytest.mark.django_db

CLIENTS = GoogleContactsSetting.CLIENTS
CLIENT_GROUP = GoogleContactsSetting.CLIENT_GROUP
OFF = GoogleContactsSetting.OFF


@pytest.fixture
def people(monkeypatch):
    accounts = {}

    def build_service(user):
        if not google.is_connected(user):
            return None
        return accounts.setdefault(user.username, FakePeople(user.username))

    monkeypatch.setattr(google, "build_service", build_service)
    return accounts


@pytest.fixture
def client_contact():
    return Contact.objects.create(name="Elena Rivera", email="elena@example.com")


@pytest.fixture
def spouse():
    return Contact.objects.create(name="Marco Rivera")


@pytest.fixture
def open_matter(client_contact, spouse):
    """An Open matter whose Client group holds the client (mirrored on
    save) and the client's spouse."""
    matter = Matter.objects.create(
        name="Rivera v. Northside", status="Open", client=client_contact
    )
    Relationship.objects.create(
        matter=matter,
        contact=spouse,
        group=Group.objects.client_group(),
        role=Role.objects.create(name="Spouse"),
    )
    return matter


def _copied(user, automatic=None):
    rows = GoogleContactCopy.objects.filter(user=user)
    if automatic is not None:
        rows = rows.filter(automatic=automatic)
    return set(rows.values_list("contact__name", flat=True))


def test_clients_copies_only_the_client(user, open_matter, people):
    _connect(user)
    google.set_auto_setting(user, CLIENTS)

    assert google.sync_automatic(user) == (1, 0)
    assert _copied(user, automatic=True) == {"Elena Rivera"}


def test_client_group_copies_everyone_in_it(user, open_matter, people):
    _connect(user)
    google.set_auto_setting(user, CLIENT_GROUP)

    google.sync_automatic(user)

    assert _copied(user, automatic=True) == {"Elena Rivera", "Marco Rivera"}


def test_a_second_run_changes_nothing(user, open_matter, people):
    _connect(user)
    google.set_auto_setting(user, CLIENT_GROUP)
    google.sync_automatic(user)

    assert google.sync_automatic(user) == (0, 0)
    assert len(people["Ollie"].created) == 2


@pytest.mark.parametrize("status", ["Pending", "Complete", "Closed"])
def test_only_open_matters_count(user, open_matter, people, status):
    open_matter.status = status
    open_matter.save()
    _connect(user)
    google.set_auto_setting(user, CLIENT_GROUP)

    assert google.sync_automatic(user) == (0, 0)


def test_closing_the_matter_removes_what_kosmos_added(
    user, open_matter, people, client_contact
):
    _connect(user)
    google.set_auto_setting(user, CLIENT_GROUP)
    google.sync_automatic(user)

    open_matter.status = "Closed"
    open_matter.save()

    assert google.sync_automatic(user) == (0, 2)
    assert _copied(user) == set()
    assert len(people["Ollie"].deleted) == 2


def test_a_contact_still_on_another_open_matter_stays(
    user, open_matter, people, client_contact
):
    Matter.objects.create(name="Rivera estate", status="Open", client=client_contact)
    _connect(user)
    google.set_auto_setting(user, CLIENTS)
    google.sync_automatic(user)

    open_matter.status = "Closed"
    open_matter.save()

    google.sync_automatic(user)
    assert _copied(user) == {"Elena Rivera"}


def test_copies_made_with_the_button_are_never_removed(
    user, open_matter, people, client_contact
):
    _connect(user)
    google.copy(user, client_contact)
    google.set_auto_setting(user, CLIENTS)
    google.sync_automatic(user)
    assert _copied(user, automatic=False) == {"Elena Rivera"}

    open_matter.status = "Closed"
    open_matter.save()
    google.set_auto_setting(user, OFF)

    assert google.sync_automatic(user) == (0, 0)
    assert _copied(user) == {"Elena Rivera"}


def test_off_removes_the_automatic_copies(user, open_matter, people):
    _connect(user)
    google.set_auto_setting(user, CLIENT_GROUP)
    google.sync_automatic(user)

    google.set_auto_setting(user, OFF)

    assert google.sync_automatic(user) == (0, 2)


def test_only_matters_the_user_can_see(open_matter, people):
    limited = CustomUser.objects.create(
        username="Limited", perm_all_matters=False, google_contacts_credentials=TOKEN
    )
    google.set_auto_setting(limited, CLIENTS)

    assert google.sync_automatic(limited) == (0, 0)

    open_matter.members.add(limited)
    assert google.sync_automatic(limited) == (1, 0)


def test_nothing_happens_without_a_connection(user, open_matter, people):
    google.set_auto_setting(user, CLIENTS)

    assert google.sync_automatic(user) == (0, 0)
    assert not GoogleContactCopy.objects.exists()


def test_the_job_runs_for_each_user_who_chose_it(user, open_matter, people):
    _connect(user)
    google.set_auto_setting(user, CLIENTS)
    CustomUser.objects.create(username="Rosa", google_contacts_credentials=TOKEN)

    summary = google.scheduled_sync_automatic()

    assert summary == {"users": 1, "added": 1, "removed": 0}


# --- the button and the setting ------------------------------------------------


def test_the_button_will_not_remove_an_automatic_copy(
    client, user, open_matter, people, client_contact
):
    _connect(user)
    google.set_auto_setting(user, CLIENTS)
    google.sync_automatic(user)

    response = client.post(
        reverse("contacts:toggle-google-sync", args=[client_contact.id]),
        HTTP_HX_REQUEST="true",
    )

    assert (
        "added this contact automatically"
        in json.loads(response.headers["HX-Toast"])["message"]
    )
    assert _copied(user) == {"Elena Rivera"}


def test_choosing_saves_and_queues_a_run(client, user, people, monkeypatch):
    _connect(user)
    queued = []
    monkeypatch.setattr(
        "apps.settings.integrations.views.async_task",
        lambda name, *args: queued.append((name, args)),
    )

    response = client.post(
        reverse("settings:google-contacts-auto"), {"auto": CLIENT_GROUP}
    )

    assert response.status_code == 200
    assert google.auto_setting(user) == CLIENT_GROUP
    assert queued == [("apps.contacts.google.sync_automatic_task", (user.id,))]
    page = " ".join(response.content.decode().split())
    assert 'value="client_group" selected' in page


def test_an_unknown_choice_or_no_connection_is_refused(client, user, monkeypatch):
    monkeypatch.setattr("apps.settings.integrations.views.async_task", lambda *a: None)
    url = reverse("settings:google-contacts-auto")

    assert client.post(url, {"auto": CLIENTS}).status_code == 400
    _connect(user)
    assert client.post(url, {"auto": "everyone"}).status_code == 400
    assert google.auto_setting(user) == OFF


def test_disconnecting_removes_the_automatic_copies_and_keeps_the_rest(
    client, user, open_matter, people, client_contact, spouse
):
    _connect(user)
    google.copy(user, spouse)
    google.set_auto_setting(user, CLIENTS)
    google.sync_automatic(user)

    client.post(reverse("settings:google-logout", args=["contacts"]))

    assert people["Ollie"].deleted == ["people/Ollie2"]
    assert google.auto_setting(user) == OFF
    assert not GoogleContactCopy.objects.exists()
