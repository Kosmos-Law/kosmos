"""Contact.user is the user who last saved the contact, not its owner: the
address book is the firm's. Deleting that user row (CASCADE, before) took
every contact they had last touched with it."""

import pytest

from apps.accounts.models import CustomUser

pytestmark = pytest.mark.django_db


def test_deleting_the_last_editor_keeps_the_contact(contact):
    editor = CustomUser.objects.create(username="editor", user_rate=100)
    contact.user = editor
    contact.save()

    editor.delete()

    contact.refresh_from_db()
    assert contact.user is None


def test_a_contact_with_no_editor_still_lists_and_opens(client, contact):
    contact.user = None
    contact.save()

    assert client.get("/contacts/").status_code == 200
    page = client.get(f"/contacts/{contact.id}/details")
    assert page.status_code == 200
    assert contact.name in page.content.decode()


def test_the_next_save_records_its_editor(client, user, contact):
    contact.user = None
    contact.save()

    client.post(
        f"/contacts/{contact.id}/edit",
        {"name": contact.name, "folder": contact.folder_id or ""},
        HTTP_HX_REQUEST="true",
    )

    contact.refresh_from_db()
    assert contact.user == user
