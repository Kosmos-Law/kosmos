"""A Paid invoice whose payment or credit is taken off goes back to the
status it was paid from: a Deferred invoice stays deferred. When the history
cannot say, it goes back to Sent."""

from decimal import Decimal

import pytest

from apps.activity.time.models import TimeEntry
from apps.invoicing.applications.models import CreditApplication, PaymentApplication
from apps.invoicing.credits.models import Credit
from apps.invoicing.invoices.models import Invoice
from apps.invoicing.payments.models import Payment

pytestmark = pytest.mark.django_db


def _invoice(user, matter, status):
    """An issued invoice for $200 of work."""
    invoice = Invoice.objects.create(
        created_by=user,
        matter=matter,
        date_limit="2024-12-31",
        date_issued="2024-12-01",
        status=status,
    )
    TimeEntry.objects.create(
        user=user,
        matter=matter,
        date="2024-11-07",
        actions="Billable work",
        hours=Decimal("1.0"),
        rate=200,
        comp=False,
        entered=False,
        invoice=invoice,
    )
    return invoice


def _pay_in_full(invoice):
    payment = Payment.objects.create(
        matter=invoice.matter,
        date="2024-12-15",
        amount=invoice.amount_remaining,
        payment_method="CHECK",
    )
    return PaymentApplication.objects.create(
        payment=payment, invoice=invoice, amount_applied=payment.amount
    )


def test_deferred_invoice_reopens_as_deferred(user, matter):
    invoice = _invoice(user, matter, "SENT")
    invoice.status = "DEFERRED"
    invoice.save()
    application = _pay_in_full(invoice)
    invoice.refresh_from_db()
    assert invoice.status == "PAID"

    application.delete()

    invoice.refresh_from_db()
    assert invoice.status == "DEFERRED"


def test_sent_invoice_reopens_as_sent(user, matter):
    invoice = _invoice(user, matter, "SENT")
    application = _pay_in_full(invoice)

    application.delete()

    invoice.refresh_from_db()
    assert invoice.status == "SENT"


def test_credit_taken_off_deferred_invoice_reopens_as_deferred(user, matter):
    invoice = _invoice(user, matter, "DEFERRED")
    credit = Credit.objects.create(
        matter=matter,
        date="2024-12-15",
        amount=invoice.amount_remaining,
        detail="Courtesy",
    )
    application = CreditApplication.objects.create(
        credit=credit, invoice=invoice, amount_applied=credit.amount
    )
    invoice.refresh_from_db()
    assert invoice.status == "PAID"

    application.delete()

    invoice.refresh_from_db()
    assert invoice.status == "DEFERRED"


def test_paid_with_no_open_history_reopens_as_sent(user, matter):
    """An invoice that was never Sent or Deferred (created Paid, as imported
    ones were) has nothing to go back to but Sent."""
    invoice = _invoice(user, matter, "PAID")
    payment = Payment.objects.create(
        matter=matter,
        date="2024-12-15",
        amount=Decimal("60.00"),
        payment_method="CHECK",
    )
    application = PaymentApplication.objects.create(
        payment=payment, invoice=invoice, amount_applied=Decimal("60.00")
    )

    application.delete()

    invoice.refresh_from_db()
    assert invoice.status == "SENT"


def test_status_before_paid_skips_an_earlier_payment(user, matter):
    """Paid, reopened to Sent, deferred, paid again: the status before the
    latest Paid is Deferred, not the Sent from the first time round."""
    invoice = _invoice(user, matter, "SENT")
    _pay_in_full(invoice).delete()
    invoice.refresh_from_db()
    assert invoice.status == "SENT"
    invoice.status = "DEFERRED"
    invoice.save()
    application = _pay_in_full(invoice)

    application.delete()

    invoice.refresh_from_db()
    assert invoice.status == "DEFERRED"
