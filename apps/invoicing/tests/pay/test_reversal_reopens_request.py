"""A payment request paid by money that later falls through (an ACH return,
a failed or voided charge) is not paid: it goes back to Sent."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.invoicing.pay.reconcile import _reverse_deposit, _reverse_payment
from apps.invoicing.payments.models import Payment
from apps.invoicing.requests.models import PaymentRequest
from apps.trust.models import Transaction

pytestmark = pytest.mark.django_db

RETURNED = SimpleNamespace(status="returned", transaction_id="txn-1")


def test_a_returned_payment_reopens_its_request(matter):
    payment = Payment.objects.create(
        matter=matter, date="2024-01-01", amount=Decimal("100.00"), payment_method="ACH"
    )
    request = PaymentRequest.objects.create(
        account="operating",
        matter=matter,
        amount_requested=Decimal("100.00"),
        recipient_email="client@example.test",
        status="PAID",
        payment=payment,
    )

    _reverse_payment(payment, RETURNED)

    request.refresh_from_db()
    assert request.status == "SENT"
    assert request.payment is None


@pytest.mark.parametrize("confirmed", [False, True])
def test_a_returned_trust_deposit_reopens_its_request(contact, confirmed):
    deposit = Transaction.objects.create(
        contact=contact,
        date="2024-01-01",
        type="Deposit",
        amount=Decimal("250.00"),
        confirmed=confirmed,
        processor_status="succeeded",
    )
    request = PaymentRequest.objects.create(
        account="trust",
        client=contact,
        amount_requested=Decimal("250.00"),
        recipient_email="client@example.test",
        status="PAID",
        trust_transaction=deposit,
    )

    _reverse_deposit(deposit, RETURNED)

    request.refresh_from_db()
    assert request.status == "SENT"
    # An unconfirmed deposit is dropped; a confirmed one is kept and flagged.
    kept = Transaction.objects.filter(pk=deposit.pk).first()
    assert (kept is not None) is confirmed
    if kept:
        assert kept.fell_through


def test_a_request_paid_by_other_money_is_left_alone(matter):
    paid_by = Payment.objects.create(
        matter=matter,
        date="2024-01-01",
        amount=Decimal("100.00"),
        payment_method="CARD",
    )
    returned = Payment.objects.create(
        matter=matter, date="2024-01-02", amount=Decimal("50.00"), payment_method="ACH"
    )
    request = PaymentRequest.objects.create(
        account="operating",
        matter=matter,
        amount_requested=Decimal("100.00"),
        recipient_email="client@example.test",
        status="PAID",
        payment=paid_by,
    )

    _reverse_payment(returned, RETURNED)

    request.refresh_from_db()
    assert request.status == "PAID"
