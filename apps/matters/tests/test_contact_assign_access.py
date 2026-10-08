"""The matter's Contacts tab: a user limited to assigned matters can add,
open, change and remove parties only on those matters.

These four views name their matter in the POST body or through the party
row, not in the URL, so the URL-based check their neighbours use never saw
them.
"""

import json

import pytest
from django.test import Client

from apps.accounts.models import CustomUser
from apps.matters.models import Matter, Relationship, Role

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_matter(practice_area):
    return Matter.objects.create(
        name="Unassigned Matter", status="Open", practice_area=practice_area
    )


@pytest.fixture
def other_relationship(other_matter, contact, role, group):
    return Relationship.objects.create(
        matter=other_matter, contact=contact, role=role, group=group
    )


@pytest.fixture
def restricted(matter):
    """A user limited to assigned matters, assigned only ``matter``."""
    user = CustomUser.objects.create(
        username="Rae", email="rae@example.com", perm_all_matters=False
    )
    user.set_password("clawboy")
    user.save()
    matter.members.add(user)
    return user


@pytest.fixture
def restricted_client(restricted):
    client = Client()
    client.force_login(restricted)
    client.get("/dash/")
    return client


def test_assign_store_refuses_another_matter(
    restricted_client, other_matter, contact, role, group
):
    data = {
        "matter_id": other_matter.id,
        "contact_id": contact.id,
        "role_id": role.id,
        "group_id": group.id,
    }

    response = restricted_client.post("/matters/assign/store", data)

    assert response.status_code == 403
    assert not Relationship.objects.filter(matter=other_matter).exists()


def test_assign_edit_refuses_another_matter(restricted_client, other_relationship):
    response = restricted_client.get(f"/matters/assign/{other_relationship.id}/edit")

    assert response.status_code == 403


def test_assign_update_refuses_another_matter(
    restricted_client, other_relationship, group
):
    new_role = Role.objects.create(name="Guardian")

    response = restricted_client.post(
        f"/matters/assign/{other_relationship.id}/update",
        {"role_id": new_role.id, "group_id": group.id},
    )

    assert response.status_code == 403
    other_relationship.refresh_from_db()
    assert other_relationship.role_id != new_role.id


def test_assign_delete_refuses_another_matter(restricted_client, other_relationship):
    response = restricted_client.post(f"/matters/assign/{other_relationship.id}/delete")

    assert response.status_code == 403
    assert Relationship.objects.filter(pk=other_relationship.pk).exists()


def test_the_users_own_matter_still_works(
    restricted_client, matter, contact, relationship, group
):
    witness = Role.objects.create(name="Witness")
    guardian = Role.objects.create(name="Guardian")

    stored = restricted_client.post(
        "/matters/assign/store",
        {
            "matter_id": matter.id,
            "contact_id": contact.id,
            "role_id": witness.id,
            "group_id": group.id,
        },
    )
    opened = restricted_client.get(f"/matters/assign/{relationship.id}/edit")
    updated = restricted_client.post(
        f"/matters/assign/{relationship.id}/update",
        {"role_id": guardian.id, "group_id": group.id},
    )
    deleted = restricted_client.post(f"/matters/assign/{relationship.id}/delete")

    assert (stored.status_code, opened.status_code) == (204, 200)
    assert (updated.status_code, deleted.status_code) == (204, 204)
    assert Relationship.objects.filter(matter=matter, role=witness).exists()
    assert not Relationship.objects.filter(pk=relationship.pk).exists()


def test_assigning_the_same_row_twice_makes_one(client, matter, contact, group):
    witness = Role.objects.create(name="Witness")
    data = {
        "matter_id": matter.id,
        "contact_id": contact.id,
        "role_id": witness.id,
        "group_id": group.id,
    }

    client.post("/matters/assign/store", data)
    response = client.post("/matters/assign/store", data)

    assert response.status_code == 204
    assert "already on" in json.loads(response.headers["HX-Toast"])["message"]
    assert Relationship.objects.filter(matter=matter, role=witness).count() == 1
