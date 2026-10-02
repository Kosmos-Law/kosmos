"""The middle list on the Contacts page always matches an entry the sidebar
highlights: a Clients list, a folder, or Unsorted. A contact that is not a
client has no Clients list, and used to leave the page on a hidden
"Nonclient" list with nothing highlighted.
"""

import pytest
from django.urls import reverse

from apps.contacts.models import Contact
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


def _state(client):
    session = client.session
    return (
        session.get("contacts_client_status"),
        session.get("contacts_selected_folder_id"),
    )


def _set(client, **values):
    session = client.session
    for key, value in values.items():
        session[key] = value
    session.save()


def test_adding_a_contact_with_no_folder_shows_unsorted(client):
    response = client.post(
        "/contacts/add", {"name": "Loose Leaf"}, HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 204
    assert _state(client) == (None, None)
    new = Contact.objects.get(name="Loose Leaf")
    page = client.get(reverse("contacts:detail-details", args=[new.id]))
    assert new in page.context["contacts"]


def test_adding_a_contact_from_an_intake_shows_pending(client, intake):
    client.post(
        "/contacts/add",
        {"name": "From Intake", "intake_id": intake.id},
        HTTP_HX_REQUEST="true",
    )

    assert _state(client) == ("Pending", None)
    new = Contact.objects.get(name="From Intake")
    page = client.get(reverse("contacts:detail-details", args=[new.id]))
    assert new in page.context["contacts"]


def test_adding_a_contact_to_a_folder_shows_the_folder(client, folder):
    _set(client, contacts_client_status="Current")

    client.post(
        "/contacts/add",
        {"name": "Filed Away", "folder": folder.id},
        HTTP_HX_REQUEST="true",
    )

    assert _state(client) == (None, folder.id)


def test_opening_a_nonclient_from_a_clients_list_shows_its_folder(
    client, contact, folder
):
    _set(client, contacts_client_status="Current")

    client.get(reverse("contacts:select", args=[contact.id]))

    assert _state(client) == (None, folder.id)


def test_opening_a_nonclient_with_no_folder_shows_unsorted(client, user):
    loose = Contact.objects.create(user=user, name="Loose Leaf")
    _set(client, contacts_client_status="Former")

    client.get(reverse("contacts:select", args=[loose.id]))

    assert _state(client) == (None, None)


def test_opening_a_client_from_a_clients_list_follows_its_status(
    client, contact, practice_area
):
    Matter.objects.create(
        name="Closed Out", status="Closed", client=contact, practice_area=practice_area
    )
    _set(client, contacts_client_status="Current")

    client.get(reverse("contacts:select", args=[contact.id]))

    assert _state(client) == ("Former", None)


def test_a_stored_nonclient_state_is_dropped(client, user):
    """A session saved before the fix: the list falls back to Unsorted, which
    the sidebar highlights."""
    loose = Contact.objects.create(user=user, name="Loose Leaf")
    _set(client, contacts_client_status="Nonclient")

    response = client.get(reverse("contacts:index"))

    assert response.context["client_status"] is None
    assert loose in response.context["contacts"]
    assert _state(client) == (None, None)
