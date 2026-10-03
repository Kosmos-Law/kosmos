"""Deleting a contact deletes what hangs off it. A contact the firm has to
keep (a client, or one with trust activity) is not deleted, whether asked
for directly or by deleting its folder."""

from decimal import Decimal

import pytest

from apps.contacts.models import Contact
from apps.folders.models import Folder
from apps.matters.models import Matter
from apps.trust.models import Transaction

pytestmark = pytest.mark.django_db


def _toast(response):
    return response.headers.get("HX-Toast", "")


def test_a_plain_contact_is_deleted_and_the_page_goes_back_to_the_list(client, contact):
    response = client.delete(f"/contacts/{contact.id}/delete")

    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/contacts/"
    assert not Contact.objects.filter(pk=contact.pk).exists()


def test_a_link_cannot_delete_a_contact(client, contact):
    response = client.get(f"/contacts/{contact.id}/delete")

    assert response.status_code == 405
    assert Contact.objects.filter(pk=contact.pk).exists()


def test_a_client_is_not_deleted(client, contact, practice_area):
    Matter.objects.create(
        name="Rivera v. Northside Logistics",
        status="Closed",
        client=contact,
        practice_area=practice_area,
    )

    response = client.delete(f"/contacts/{contact.id}/delete")

    assert response.status_code == 204
    assert Contact.objects.filter(pk=contact.pk).exists()
    assert "is the client on 1 matter" in _toast(response)


def test_a_contact_with_trust_activity_is_not_deleted(client, contact):
    Transaction.objects.create(
        contact=contact, date="2024-01-02", type="Deposit", amount=Decimal("500.00")
    )

    response = client.delete(f"/contacts/{contact.id}/delete")

    assert Contact.objects.filter(pk=contact.pk).exists()
    assert Transaction.objects.filter(contact=contact).count() == 1
    assert "has trust activity" in _toast(response)


def test_deleting_a_folder_and_its_contacts_keeps_the_ones_that_matter(
    client, user, folder, contact
):
    Transaction.objects.create(
        contact=contact, date="2024-01-02", type="Deposit", amount=Decimal("500.00")
    )
    plain = Contact.objects.create(user=user, folder=folder, name="Plain Contact")

    response = client.delete(f"/folders/delete/{folder.id}?delete_contacts=true")

    assert response.status_code == 204
    assert not Folder.objects.filter(pk=folder.pk).exists()
    assert not Contact.objects.filter(pk=plain.pk).exists()
    contact.refresh_from_db()
    assert contact.folder is None
    assert Transaction.objects.filter(contact=contact).count() == 1
    assert "Kept 1 contact" in _toast(response)


def test_a_link_cannot_delete_a_folder(client, folder):
    response = client.get(f"/folders/delete/{folder.id}?delete_contacts=true")

    assert response.status_code == 405
    assert Folder.objects.filter(pk=folder.pk).exists()
