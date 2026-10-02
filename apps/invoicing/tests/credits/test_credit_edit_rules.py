"""Editing a credit follows the rules editing a payment does: an amount is
more than zero, and a credit applied to invoices cannot shrink below what is
applied or move to another matter."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.invoicing.applications.models import CreditApplication
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def applied_credit(credit, sent_invoice):
    """The $1,000.00 credit, with $600.00 applied to an invoice."""
    CreditApplication.objects.create(
        credit=credit, invoice=sent_invoice, amount_applied=Decimal("600.00")
    )
    return credit


def _edit(client, credit, **changes):
    data = {
        "matter": credit.matter_id,
        "date": "2024-12-15",
        "amount": "1000.00",
        "detail": "Test credit",
    }
    data.update(changes)
    return client.post(reverse("invoicing:credits-edit", args=[credit.pk]), data)


@pytest.mark.parametrize("amount", ["0", "-25.00"])
def test_an_amount_must_be_more_than_zero(client, credit, amount):
    response = _edit(client, credit, amount=amount)

    assert response.status_code == 200
    assert "greater than zero" in str(response.context["form"].errors)
    credit.refresh_from_db()
    assert credit.amount == Decimal("1000.00")


def test_an_applied_credit_cannot_shrink_below_what_is_applied(client, applied_credit):
    response = _edit(client, applied_credit, amount="599.99")

    assert response.status_code == 200
    assert "$600.00 of this credit is applied" in str(response.context["form"].errors)
    applied_credit.refresh_from_db()
    assert applied_credit.amount == Decimal("1000.00")


def test_it_can_shrink_to_what_is_applied(client, applied_credit):
    assert _edit(client, applied_credit, amount="600.00").status_code == 204


def test_an_applied_credit_cannot_move_to_another_matter(
    client, applied_credit, practice_area
):
    other = Matter.objects.create(
        name="Another Matter", status="Open", practice_area=practice_area
    )

    response = _edit(client, applied_credit, matter=other.id)

    assert response.status_code == 200
    applied_credit.refresh_from_db()
    assert applied_credit.matter_id != other.id


def test_an_unapplied_credit_can_move(client, credit, practice_area):
    other = Matter.objects.create(
        name="Another Matter", status="Open", practice_area=practice_area
    )

    assert _edit(client, credit, matter=other.id).status_code == 204
    credit.refresh_from_db()
    assert credit.matter_id == other.id
