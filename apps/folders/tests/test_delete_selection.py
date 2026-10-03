"""Deleting the folder that is open resets what the Contacts page is showing.

The delete address took its id as text, so comparing it with the stored
folder id and with the open contact's folder never matched: the page kept
pointing at the folder, and the contact, that had just gone.
"""

import pytest

from apps.contacts.models import Contact
from apps.folders.models import Folder

pytestmark = pytest.mark.django_db


@pytest.fixture
def folder():
    return Folder.objects.create(app="contacts", name="Experts")


def _set(client, **values):
    session = client.session
    for key, value in values.items():
        session[key] = value
    session.save()


def test_deleting_the_open_folder_forgets_it(client, folder):
    _set(client, contacts_selected_folder_id=folder.id)

    response = client.delete(f"/folders/delete/{folder.id}")

    assert response.status_code == 204
    assert "contacts_selected_folder_id" not in client.session


def test_deleting_the_open_contacts_folder_closes_the_contact(client, user, folder):
    contact = Contact.objects.create(user=user, folder=folder, name="Ada Vance")
    _set(client, selected_contact_id=contact.id)

    client.delete(f"/folders/delete/{folder.id}?keep_contacts=true")

    assert "selected_contact_id" not in client.session
    assert Contact.objects.filter(pk=contact.pk).exists()


def test_deleting_another_folder_leaves_the_page_alone(client, user, folder):
    other = Folder.objects.create(app="contacts", name="Vendors")
    contact = Contact.objects.create(user=user, folder=folder, name="Ada Vance")
    _set(
        client,
        contacts_selected_folder_id=folder.id,
        selected_contact_id=contact.id,
    )

    client.delete(f"/folders/delete/{other.id}")

    assert client.session["contacts_selected_folder_id"] == folder.id
    assert client.session["selected_contact_id"] == contact.id


def test_a_folder_address_that_is_not_a_number_is_not_found(client):
    response = client.delete("/folders/delete/abc")

    assert response.status_code == 404
