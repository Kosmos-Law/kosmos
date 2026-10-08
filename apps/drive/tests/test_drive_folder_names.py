"""The Drive Folder dialog says a folder is linked to another matter without
naming a matter the user is not on."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_matter(fake_drive):
    fake_drive.add_folder("mf2", "Doe Folder", parent="root1")
    return Matter.objects.create(
        name="Doe v Roe",
        status="Open",
        drive_folder_id="mf2",
        drive_folder="Doe Folder",
    )


@pytest.fixture
def restricted_user(matter):
    user = CustomUser.objects.create(
        username="restricted", email="restricted@example.com", perm_all_matters=False
    )
    user.set_password("pw")
    user.save()
    matter.members.add(user)
    return user


@pytest.fixture
def restricted_client(restricted_user):
    client = Client()
    client.force_login(restricted_user)
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


def _modal(client, matter):
    return client.get(
        reverse("case:documents-drive-modal", args=[matter.id])
    ).content.decode()


def _save(client, matter, folder_id):
    return client.post(
        reverse("case:documents-drive-save", args=[matter.id]),
        {"matter_folder": folder_id},
    ).content.decode()


def test_dialog_does_not_name_a_matter_the_user_is_not_on(
    restricted_client, matter, other_matter
):
    body = _modal(restricted_client, matter)

    assert "linked to another matter" in body
    assert "Doe v Roe" not in body
    # The folder is still shown, and still unavailable.
    assert "Doe Folder" in body


def test_dialog_names_a_matter_the_user_is_on(
    restricted_client, restricted_user, matter, other_matter
):
    other_matter.members.add(restricted_user)

    assert "linked to Doe v Roe" in _modal(restricted_client, matter)


def test_user_with_all_matters_sees_the_name(client, matter, other_matter):
    assert "linked to Doe v Roe" in _modal(client, matter)


def test_save_clash_does_not_name_a_matter_the_user_is_not_on(
    restricted_client, matter, other_matter
):
    body = _save(restricted_client, matter, "mf2")

    assert "already linked to another matter" in body
    assert "Doe v Roe" not in body


def test_save_clash_by_folder_name_does_not_name_the_matter(
    restricted_client, matter, other_matter
):
    # A link made before folder ids were stored clashes by name instead.
    Matter.objects.filter(pk=other_matter.pk).update(drive_folder_id=None)

    body = _save(restricted_client, matter, "mf2")

    assert "already linked to another matter" in body
    assert "Doe v Roe" not in body
