"""A matter's Ledger lists invoices, payments and credits together. Each
row's links must follow what the row is, not the words in its free-text
description."""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.invoicing.credits.models import Credit
from apps.invoicing.payments.models import Payment
from apps.matters.ledger.get_ledger_data import get_ledger_data

pytestmark = pytest.mark.django_db


def test_a_credit_described_as_a_payment_is_still_a_credit(client, matter):
    credit = Credit.objects.create(
        matter=matter,
        date=date(2020, 2, 2),
        amount=Decimal("40.00"),
        detail="Payment plan adjustment for Invoice 7",
    )

    (row,) = get_ledger_data(matter)["transactions"]
    body = client.get(reverse("matters:ledger", args=[matter.id])).content.decode()

    assert row["kind"] == "credit"
    assert reverse("invoicing:credits-delete", args=[credit.id]) in body
    # Its menu must not act on the payment, or the invoice, with the same id.
    assert reverse("invoicing:payments-delete", args=[credit.id]) not in body
    assert reverse("invoicing:invoices-detail-index", args=[credit.id]) not in body


def test_a_payment_row_acts_on_the_payment(client, matter):
    payment = Payment.objects.create(
        matter=matter,
        date=date(2020, 2, 1),
        amount=Decimal("100.00"),
        payment_method="Check",
    )

    (row,) = get_ledger_data(matter)["transactions"]
    body = client.get(reverse("matters:ledger", args=[matter.id])).content.decode()

    assert row["kind"] == "payment"
    assert reverse("invoicing:payments-delete", args=[payment.id]) in body
    assert reverse("invoicing:credits-delete", args=[payment.id]) not in body


def test_a_credit_with_no_detail_is_labelled(matter):
    Credit.objects.create(matter=matter, date=date(2020, 2, 2), amount=Decimal("40.00"))

    row = get_ledger_data(matter)["transactions"][0]

    assert row["kind"] == "credit"
    assert row["description"] == "Credit"
