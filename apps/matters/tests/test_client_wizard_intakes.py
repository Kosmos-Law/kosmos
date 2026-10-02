"""The matter form's "Convert an intake" detour shows intake names, phone
numbers and addresses. The matter form is open to everyone; intakes are for
users with the Intakes permission, so the detour asks for it.
"""

import json

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.contacts.models import Contact
from apps.intakes.models import Intake

pytestmark = pytest.mark.django_db


@pytest.fixture
def intake():
    return Intake.objects.create(
        name="Nadia Okafor",
        date="2024-03-01",
        phone="404.555.0188",
        email="nadia@example.com",
        address="12 Juniper Court",
    )


@pytest.fixture
def no_intakes(client, user):
    """The signed-in user, without the Intakes permission. An update, not a
    save: the fixture's copy predates the day's dash check-in and saving it
    would undo that, sending the next request to the dash."""
    CustomUser.objects.filter(pk=user.pk).update(perm_intakes=False)
    return user


def _search(client):
    return client.post(reverse("matters:client-search"), {"search_text": "a"})


def test_the_picker_is_refused_without_the_intakes_permission(
    client, no_intakes, intake
):
    response = client.post(reverse("matters:client-intake-picker"), {"name": "Draft"})

    assert response.status_code == 403
    assert b"Nadia Okafor" not in response.content


def test_the_prefill_is_refused_without_the_intakes_permission(
    client, no_intakes, intake
):
    response = client.get(reverse("matters:client-intake-contact", args=[intake.id]))

    assert response.status_code == 403
    assert b"nadia@example.com" not in response.content


def test_the_button_is_hidden_without_the_intakes_permission(client, no_intakes):
    body = _search(client).content.decode()

    assert "Create new contact" in body
    assert "Convert an intake" not in body


def test_linking_an_intake_is_refused_without_the_permission(
    client, no_intakes, intake
):
    response = client.post(
        reverse("matters:client-create-contact"),
        {"name": "Quiet Link", "intake_id": intake.id},
    )

    assert response.status_code == 403
    assert not Contact.objects.filter(name="Quiet Link").exists()


def test_the_detour_works_with_the_intakes_permission(client, intake):
    assert "Convert an intake" in _search(client).content.decode()

    picker = client.post(reverse("matters:client-intake-picker"), {"name": "Draft"})
    prefill = client.get(reverse("matters:client-intake-contact", args=[intake.id]))

    assert picker.status_code == 200
    assert intake in picker.context["intakes"]
    assert prefill.context["form"].initial["email"] == "nadia@example.com"


def test_an_admin_does_not_need_the_permission(client, no_intakes, intake):
    CustomUser.objects.filter(pk=no_intakes.pk).update(role="ADMIN")

    response = client.post(reverse("matters:client-intake-picker"), {"name": "Draft"})

    assert response.status_code == 200


def test_an_intake_already_in_contacts_is_not_converted_twice(client, user, intake):
    """Two people pick the same intake: the second submit adds no twin."""
    Contact.objects.create(user=user, name="Nadia Okafor", intake=intake)

    response = client.post(
        reverse("matters:client-create-contact"),
        {"name": "Nadia Okafor", "intake_id": intake.id},
    )

    assert response.status_code == 204
    assert "already in contacts" in json.loads(response.headers["HX-Toast"])["message"]
    assert Contact.objects.filter(intake=intake).count() == 1
