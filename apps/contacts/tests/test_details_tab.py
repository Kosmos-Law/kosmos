"""What the Details tab shows. A contact's company used to sit inside the
address card only, so a contact with no address never showed it."""

import pytest
from django.urls import reverse

from apps.contacts.models import Contact

pytestmark = pytest.mark.django_db


def _details(client, contact):
    response = client.get(reverse("contacts:detail-details", args=[contact.id]))
    body = response.content.decode()
    # The hidden copy-all block also carries the company: look past it.
    return body.split('id="contact-full-details"', 1)[1].split("</div>", 1)[1]


def test_company_is_shown_without_an_address(client, user):
    contact = Contact.objects.create(user=user, name="Ada Vance", company="Vance & Co")

    visible = _details(client, contact)

    assert "Vance &amp; Co" in visible
    assert "Open in Google Maps" not in visible


def test_company_and_address_share_the_card(client, contact):
    visible = _details(client, contact)

    assert "Gandhi, PC" in visible
    assert "225 Paper Street" in visible
    assert "Open in Google Maps" in visible


def test_no_card_without_company_or_address(client, user):
    contact = Contact.objects.create(user=user, name="Ada Vance")

    assert "contact-card-text-vertical" not in _details(client, contact)
