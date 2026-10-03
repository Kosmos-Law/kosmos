"""An intake has one contact. The intake page looked it up expecting exactly
one and failed outright when two were linked, and nothing stopped a second
from being linked.
"""

import json

import pytest

from apps.contacts.models import Contact

pytestmark = pytest.mark.django_db


def _toast(response):
    return json.loads(response.headers["HX-Toast"])["message"]


def test_the_intake_page_opens_with_two_contacts_linked(client, user, intake):
    first = Contact.objects.create(user=user, name="First Twin", intake=intake)
    Contact.objects.create(user=user, name="Second Twin", intake=intake)

    page = client.get(f"/intakes/{intake.id}/")
    partial = client.get(f"/intakes/{intake.id}/detail/")

    assert (page.status_code, partial.status_code) == (200, 200)
    # The menu's Open contact goes to the earlier of the two.
    assert page.context["contact"] == first


def test_the_intake_page_opens_with_no_contact(client, intake):
    response = client.get(f"/intakes/{intake.id}/")

    assert response.status_code == 200
    assert response.context["contact"] is None


def test_a_second_contact_is_not_linked_to_the_intake(client, user, intake):
    Contact.objects.create(user=user, name="Mohandas Gandhi", intake=intake)

    response = client.post(
        "/contacts/add",
        {"name": "Mohandas Gandhi", "intake_id": intake.id},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 204
    assert "already in contacts as Mohandas Gandhi" in _toast(response)
    assert Contact.objects.filter(intake=intake).count() == 1
    assert Contact.objects.filter(name="Mohandas Gandhi").count() == 1


def test_the_first_contact_is_linked(client, intake):
    response = client.post(
        "/contacts/add",
        {"name": "Mohandas Gandhi", "intake_id": intake.id},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 204
    assert Contact.objects.get(intake=intake).name == "Mohandas Gandhi"
