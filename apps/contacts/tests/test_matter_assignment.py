"""Assign to Matter and Remove from Matter on the contact page follow the
rules of the matter's own Contacts tab: the client's row is the matter's to
manage, the Client role is not handed out, the same row is not made twice,
and a dialog with nothing chosen is answered, not crashed on.
"""

import json

import pytest

from apps.matters.models import Group, Matter, Relationship, Role

pytestmark = pytest.mark.django_db


@pytest.fixture
def system_client(db):
    """The system Client group and role the matter-client mirror uses."""
    group = Group.objects.client_group() or Group.objects.create(
        name="Client", order=1, is_system=True
    )
    role = Role.objects.client_role() or Role.objects.create(
        name="Client", is_system=True
    )
    return group, role


@pytest.fixture
def party_group():
    return Group.objects.create(name="Opposing Party", order=2)


@pytest.fixture
def party_role():
    return Role.objects.create(name="Witness")


@pytest.fixture
def client_matter(system_client, contact, practice_area):
    """A matter whose client is ``contact``: saving writes the mirror row."""
    return Matter.objects.create(
        name="Gandhi v. Empire",
        status="Open",
        client=contact,
        practice_area=practice_area,
    )


def _mirror(matter, contact):
    return Relationship.objects.get(
        matter=matter, contact=contact, role__is_system=True
    )


def _toast(response):
    return json.loads(response.headers["HX-Toast"])["message"]


# -----------------------------------------------------
# remove: the client's own row
# -----------------------------------------------------
def test_remove_refuses_the_clients_own_row(client, contact, client_matter):
    mirror = _mirror(client_matter, contact)

    response = client.post("/contacts/remove/store", {"relationship_id": mirror.id})

    assert response.status_code == 403
    assert Relationship.objects.filter(pk=mirror.pk).exists()


def test_remove_does_not_offer_the_clients_own_row(
    client, contact, client_matter, party_group, party_role
):
    second = Relationship.objects.create(
        matter=client_matter, contact=contact, group=party_group, role=party_role
    )

    response = client.get(f"/contacts/{contact.id}/remove")

    assert response.context["relationships"] == [second]


def test_remove_still_removes_another_role_on_the_clients_matter(
    client, contact, client_matter, party_group, party_role
):
    second = Relationship.objects.create(
        matter=client_matter, contact=contact, group=party_group, role=party_role
    )

    response = client.post("/contacts/remove/store", {"relationship_id": second.id})

    assert response.status_code == 302
    assert not Relationship.objects.filter(pk=second.pk).exists()
    assert Relationship.objects.filter(pk=_mirror(client_matter, contact).pk).exists()


# -----------------------------------------------------
# assign: roles offered, duplicates
# -----------------------------------------------------
def test_assign_does_not_offer_the_client_roles(client, contact, system_client):
    _, client_role = system_client
    invoicing = Role.objects.create(name="Client (Invoicing)")
    witness = Role.objects.create(name="Witness")

    response = client.get(f"/contacts/{contact.id}/assign")

    roles = list(response.context["roles"])
    assert witness in roles
    assert client_role not in roles
    assert invoicing not in roles


def test_assign_refuses_the_system_client_role(
    client, contact, matter, party_group, system_client
):
    _, client_role = system_client
    data = {
        "matter_id": matter.id,
        "group_id": party_group.id,
        "role_id": client_role.id,
    }

    response = client.post(f"/contacts/{contact.id}/assign/store", data)

    assert response.status_code == 404
    assert not Relationship.objects.filter(matter=matter, contact=contact).exists()


def test_assigning_the_same_row_twice_makes_one(
    client, contact, matter, party_group, party_role
):
    data = {
        "matter_id": matter.id,
        "group_id": party_group.id,
        "role_id": party_role.id,
    }
    url = f"/contacts/{contact.id}/assign/store"

    client.post(url, data, HTTP_HX_REQUEST="true")
    response = client.post(url, data, HTTP_HX_REQUEST="true")

    assert response.status_code == 204
    assert "already on" in _toast(response)
    assert Relationship.objects.filter(matter=matter, contact=contact).count() == 1


def test_a_second_role_on_the_same_matter_is_still_allowed(
    client, contact, matter, party_group, party_role
):
    other_role = Role.objects.create(name="Guardian")
    url = f"/contacts/{contact.id}/assign/store"
    base = {"matter_id": matter.id, "group_id": party_group.id}

    client.post(url, base | {"role_id": party_role.id})
    client.post(url, base | {"role_id": other_role.id})

    assert Relationship.objects.filter(matter=matter, contact=contact).count() == 2


def test_assign_from_the_dialog_goes_to_all_matters(
    client, contact, matter, party_group, party_role
):
    data = {
        "matter_id": matter.id,
        "group_id": party_group.id,
        "role_id": party_role.id,
    }

    response = client.post(
        f"/contacts/{contact.id}/assign/store", data, HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == f"/contacts/{contact.id}/matters"


# -----------------------------------------------------
# assign: the group belongs to the matter
# -----------------------------------------------------
def test_assign_refuses_another_matters_own_group(
    client, contact, matter, party_role, practice_area
):
    elsewhere = Matter.objects.create(
        name="Elsewhere", status="Open", practice_area=practice_area
    )
    theirs = Group.objects.create(
        name="Elsewhere's Insurers",
        order=Group.MATTER_GROUP_ORDER_BASE + 1,
        matter=elsewhere,
    )
    data = {"matter_id": matter.id, "group_id": theirs.id, "role_id": party_role.id}

    response = client.post(f"/contacts/{contact.id}/assign/store", data)

    assert response.status_code == 404
    assert not Relationship.objects.filter(matter=matter, contact=contact).exists()


def test_assign_accepts_the_matters_own_group(client, contact, matter, party_role):
    own = Group.objects.create(
        name="Insurers", order=Group.MATTER_GROUP_ORDER_BASE + 1, matter=matter
    )
    data = {"matter_id": matter.id, "group_id": own.id, "role_id": party_role.id}

    response = client.post(f"/contacts/{contact.id}/assign/store", data)

    assert response.status_code == 302
    assert Relationship.objects.filter(matter=matter, group=own).exists()


# -----------------------------------------------------
# empty dropdowns
# -----------------------------------------------------
def test_assign_with_nothing_chosen_is_answered(client, contact):
    response = client.post(
        f"/contacts/{contact.id}/assign/store", {}, HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 204
    assert "Choose a matter" in _toast(response)


def test_assign_with_ids_that_are_not_numbers_is_answered(client, contact):
    data = {"matter_id": "abc", "group_id": "1", "role_id": "1"}

    response = client.post(
        f"/contacts/{contact.id}/assign/store", data, HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 204
    assert "Choose a matter" in _toast(response)


def test_assign_with_no_open_matter_cannot_be_submitted(client, contact):
    Matter.objects.update(status="Closed")

    response = client.get(f"/contacts/{contact.id}/assign")

    body = response.content.decode()
    assert "no open matters" in body
    assert "disabled" in body


def test_remove_with_nothing_chosen_is_answered(client, contact):
    response = client.post(
        "/contacts/remove/store", {"contact_id": contact.id}, HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 204
    assert "Choose a matter" in _toast(response)


def test_remove_with_no_matter_cannot_be_submitted(client, contact):
    response = client.get(f"/contacts/{contact.id}/remove")

    body = response.content.decode()
    assert "no matter to remove" in body
    assert "disabled" in body
