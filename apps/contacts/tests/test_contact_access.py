"""What a contact page shows and lets a user do depends on who is looking.

Contacts are the firm's: everyone sees them. A user limited to assigned
matters sees only those matters on a contact, and can put the contact on or
take it off only those. A client's trust balances are for users with the
Financial permission, and an intake's details for users with Intakes.
"""

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.contacts.models import Contact
from apps.matters.models import Matter, Relationship, Role
from apps.trust.models import Transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_matter(practice_area):
    return Matter.objects.create(
        name="Unassigned Matter", status="Open", practice_area=practice_area
    )


@pytest.fixture
def party_role():
    return Role.objects.create(name="Witness")


@pytest.fixture
def on_both(contact, matter, other_matter, group, party_role):
    """The contact is a party on the user's matter and on one that is not."""
    mine = Relationship.objects.create(
        matter=matter, contact=contact, group=group, role=party_role
    )
    theirs = Relationship.objects.create(
        matter=other_matter, contact=contact, group=group, role=party_role
    )
    return mine, theirs


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
    client.login(username="Rae", password="clawboy")
    client.get("/dash/")
    return client


def _set(user, **fields):
    """Change the signed-in user's permissions. An update, not a save: the
    fixture's copy predates the day's dash check-in and saving it would undo
    that, sending the next request to the dash."""
    CustomUser.objects.filter(pk=user.pk).update(**fields)


def _matters(response, key):
    return [r.matter for r in response.context[key]]


# -----------------------------------------------------
# matters on the contact page
# -----------------------------------------------------
def test_all_matters_lists_only_the_users_matters(
    restricted_client, contact, matter, on_both
):
    response = restricted_client.get(
        reverse("contacts:detail-matters", args=[contact.id])
    )

    assert _matters(response, "relationships") == [matter]
    assert "Unassigned Matter" not in response.content.decode()


def test_open_matters_lists_only_the_users_matters(
    restricted_client, contact, matter, on_both
):
    response = restricted_client.get(
        reverse("contacts:detail-details", args=[contact.id])
    )

    assert _matters(response, "open_matters") == [matter]
    assert "Unassigned Matter" not in response.content.decode()


def test_a_client_matter_without_a_party_row_is_hidden_too(
    restricted_client, contact, other_matter
):
    """The stand-in row for Matter.client is filtered like the real ones."""
    other_matter.client = contact
    other_matter.save()
    Relationship.objects.filter(matter=other_matter).delete()

    response = restricted_client.get(
        reverse("contacts:detail-matters", args=[contact.id])
    )

    assert _matters(response, "relationships") == []


def test_a_user_with_all_matters_sees_every_matter(
    client, contact, matter, other_matter, on_both
):
    response = client.get(reverse("contacts:detail-matters", args=[contact.id]))

    assert set(_matters(response, "relationships")) == {matter, other_matter}


# -----------------------------------------------------
# assign to matter, remove from matter
# -----------------------------------------------------
def test_assign_offers_only_the_users_matters(
    restricted_client, contact, matter, other_matter
):
    response = restricted_client.get(f"/contacts/{contact.id}/assign")

    assert list(response.context["matters"]) == [matter]


def test_assign_refuses_a_matter_the_user_is_not_on(
    restricted_client, contact, other_matter, group, party_role
):
    data = {
        "matter_id": other_matter.id,
        "group_id": group.id,
        "role_id": party_role.id,
    }

    response = restricted_client.post(f"/contacts/{contact.id}/assign/store", data)

    assert response.status_code == 403
    assert not Relationship.objects.filter(matter=other_matter).exists()


def test_assign_works_on_the_users_own_matter(
    restricted_client, contact, matter, group, party_role
):
    data = {"matter_id": matter.id, "group_id": group.id, "role_id": party_role.id}

    response = restricted_client.post(f"/contacts/{contact.id}/assign/store", data)

    assert response.status_code == 302
    assert Relationship.objects.filter(matter=matter, contact=contact).exists()


def test_remove_offers_only_the_users_matters(restricted_client, contact, on_both):
    mine, _ = on_both

    response = restricted_client.get(f"/contacts/{contact.id}/remove")

    assert response.context["relationships"] == [mine]


def test_remove_refuses_a_matter_the_user_is_not_on(
    restricted_client, contact, on_both
):
    _, theirs = on_both

    response = restricted_client.post(
        "/contacts/remove/store", {"relationship_id": theirs.id}
    )

    assert response.status_code == 403
    assert Relationship.objects.filter(pk=theirs.pk).exists()


def test_remove_works_on_the_users_own_matter(restricted_client, contact, on_both):
    mine, _ = on_both

    response = restricted_client.post(
        "/contacts/remove/store", {"relationship_id": mine.id}
    )

    assert response.status_code == 302
    assert not Relationship.objects.filter(pk=mine.pk).exists()


# -----------------------------------------------------
# trust tab
# -----------------------------------------------------
@pytest.fixture
def client_with_trust(contact, matter):
    matter.client = contact
    matter.save()
    Transaction.objects.create(
        contact=contact, date="2024-01-02", type="Deposit", amount=Decimal("4321.00")
    )
    return contact


def test_trust_tab_is_refused_without_the_financial_permission(
    client, user, client_with_trust
):
    _set(user, perm_financial=False)

    response = client.get(reverse("contacts:detail-trust", args=[client_with_trust.id]))

    assert response.status_code == 403


def test_trust_tab_is_not_offered_without_the_financial_permission(
    client, user, client_with_trust
):
    _set(user, perm_financial=False)

    response = client.get(
        reverse("contacts:detail-details", args=[client_with_trust.id])
    )

    assert response.status_code == 200
    trust_url = reverse("contacts:detail-trust", args=[client_with_trust.id])
    assert trust_url not in response.content.decode()
    # No tab carries the numbers for this user.
    assert response.context["trust"] is False
    assert response.context["confirmed_balance"] == 0


def test_trust_tab_shows_balances_with_the_financial_permission(
    client, client_with_trust
):
    details = client.get(
        reverse("contacts:detail-details", args=[client_with_trust.id])
    )
    trust = client.get(reverse("contacts:detail-trust", args=[client_with_trust.id]))

    trust_url = reverse("contacts:detail-trust", args=[client_with_trust.id])
    assert trust_url in details.content.decode()
    assert trust.status_code == 200
    assert trust.context["trust"] is True


def test_an_admin_sees_the_trust_tab_whatever_the_permission(
    client, user, client_with_trust
):
    _set(user, role="ADMIN", perm_financial=False)

    response = client.get(reverse("contacts:detail-trust", args=[client_with_trust.id]))

    assert response.status_code == 200


# -----------------------------------------------------
# intake details
# -----------------------------------------------------
def test_add_from_intake_is_refused_without_the_intakes_permission(
    client, user, intake
):
    _set(user, perm_intakes=False)

    response = client.get(f"/contacts/{intake.id}/add_intake")

    assert response.status_code == 403
    assert intake.email not in response.content.decode()


def test_add_from_intake_opens_with_the_intakes_permission(client, intake):
    response = client.get(f"/contacts/{intake.id}/add_intake")

    assert response.status_code == 200
    assert response.context["form"].initial["email"] == intake.email


def test_a_contact_cannot_be_linked_to_an_intake_without_the_permission(
    client, user, intake
):
    _set(user, perm_intakes=False)

    response = client.post(
        "/contacts/add", {"name": "Quiet Link", "intake_id": intake.id}
    )

    assert response.status_code == 403
    assert not Contact.objects.filter(name="Quiet Link").exists()
