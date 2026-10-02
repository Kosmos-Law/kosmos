"""The matter's Contacts tab changes parties with a POST only, and answers
an Assign that is missing something instead of failing.

A plain link (in an email, on another site) sends a GET: it must not add,
change or remove a party. Assign with no contact picked from the search
sends an empty id, which used to be a server error.
"""

import json
from pathlib import Path

import pytest
from django.conf import settings

from apps.matters.models import Relationship, Role

pytestmark = pytest.mark.django_db


def _toast(response):
    return json.loads(response.headers["HX-Toast"])["message"]


# -----------------------------------------------------
# POST only
# -----------------------------------------------------
def test_a_link_cannot_assign_a_contact(client, matter, contact, role, group):
    query = (
        f"?matter_id={matter.id}&contact_id={contact.id}"
        f"&role_id={role.id}&group_id={group.id}"
    )

    response = client.get(f"/matters/assign/store{query}")

    assert response.status_code == 405
    assert not Relationship.objects.filter(matter=matter, role=role).exists()


def test_a_link_cannot_change_an_assignment(client, relationship, group):
    other = Role.objects.create(name="Guardian")

    response = client.get(
        f"/matters/assign/{relationship.id}/update"
        f"?role_id={other.id}&group_id={group.id}"
    )

    assert response.status_code == 405
    relationship.refresh_from_db()
    assert relationship.role_id != other.id


def test_a_link_cannot_remove_an_assignment(client, relationship):
    response = client.get(f"/matters/assign/{relationship.id}/delete")

    assert response.status_code == 405
    assert Relationship.objects.filter(pk=relationship.pk).exists()


def test_the_unused_assign_pages_are_gone():
    """Two full-page versions of the dialogs that nothing rendered; one held
    a link that removed an assignment with a GET."""
    templates = Path(settings.BASE_DIR) / "templates" / "matters" / "contacts"

    assert not (templates / "assign.html").exists()
    assert not (templates / "assign-role.html").exists()
    assert (templates / "assign-modal.html").exists()


# -----------------------------------------------------
# Assign with something missing
# -----------------------------------------------------
def test_assign_with_no_contact_picked_is_answered(client, matter, role, group):
    data = {
        "matter_id": matter.id,
        "contact_id": "",
        "role_id": role.id,
        "group_id": group.id,
    }

    response = client.post("/matters/assign/store", data)

    assert response.status_code == 204
    assert "Choose a contact" in _toast(response)
    assert not Relationship.objects.filter(matter=matter, role=role).exists()


def test_assign_with_a_dropdown_left_on_its_prompt_is_answered(
    client, matter, contact, group
):
    data = {
        "matter_id": matter.id,
        "contact_id": contact.id,
        "role_id": "",
        "group_id": group.id,
    }

    response = client.post("/matters/assign/store", data)

    assert response.status_code == 204
    assert "Choose a contact" in _toast(response)


def test_assign_with_no_matter_is_answered(client, contact, role, group):
    data = {"contact_id": contact.id, "role_id": role.id, "group_id": group.id}

    response = client.post("/matters/assign/store", data)

    assert response.status_code == 204
    assert "lost track of its matter" in _toast(response)
    assert not Relationship.objects.filter(contact=contact, role=role).exists()


def test_a_complete_assign_still_works(client, matter, contact, group):
    witness = Role.objects.create(name="Witness")
    data = {
        "matter_id": matter.id,
        "contact_id": contact.id,
        "role_id": witness.id,
        "group_id": group.id,
    }

    response = client.post("/matters/assign/store", data)

    assert response.status_code == 204
    assert response.headers["HX-Trigger"] == "contactsReload"
    assert Relationship.objects.filter(matter=matter, role=witness).exists()
