"""Taking a payment or a credit off an invoice. A Paid invoice that is no
longer covered goes back to Sent, however the money is removed; and a
change or delete here needs a POST or DELETE, never a plain link."""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.activity.time.models import TimeEntry
from apps.invoicing.applications.models import (
    CreditApplication,
    PaymentApplication,
    apply_to_invoice,
)
from apps.invoicing.credits.models import Credit
from apps.invoicing.invoices.models import Invoice
from apps.invoicing.payments.models import Payment

pytestmark = pytest.mark.django_db


@pytest.fixture
def sent_invoice(user, matter):
    """A Sent invoice for $300.00 (3 hours at $100)."""
    invoice = Invoice.objects.create(
        matter=matter,
        date_limit=date(2020, 1, 31),
        date_issued=date(2020, 2, 1),
        status="SENT",
    )
    TimeEntry.objects.create(
        user=user,
        matter=matter,
        date="2020-01-07",
        actions="Draft the complaint",
        hours=3,
        rate=100,
        invoice=invoice,
    )
    return invoice


def _payment(matter, amount="300.00"):
    return Payment.objects.create(
        matter=matter,
        date=date(2020, 2, 5),
        amount=Decimal(amount),
        payment_method="Check",
    )


def _credit(matter, amount="300.00"):
    return Credit.objects.create(
        matter=matter, date=date(2020, 2, 5), amount=Decimal(amount), detail="Courtesy"
    )


def test_deleting_a_payment_reopens_the_invoice_it_paid(client, matter, sent_invoice):
    payment = _payment(matter)
    PaymentApplication.objects.create(
        payment=payment, invoice=sent_invoice, amount_applied=Decimal("300.00")
    )
    sent_invoice.refresh_from_db()
    assert sent_invoice.status == "PAID"

    response = client.delete(reverse("invoicing:payments-delete", args=[payment.id]))

    assert response.status_code == 204
    sent_invoice.refresh_from_db()
    assert sent_invoice.status == "SENT"
    assert sent_invoice.amount_remaining == Decimal("300.00")


def test_deleting_a_credit_reopens_the_invoice_it_paid(client, matter, sent_invoice):
    credit = _credit(matter)
    CreditApplication.objects.create(
        credit=credit, invoice=sent_invoice, amount_applied=Decimal("300.00")
    )
    sent_invoice.refresh_from_db()
    assert sent_invoice.status == "PAID"

    response = client.delete(reverse("invoicing:credits-delete", args=[credit.id]))

    assert response.status_code == 204
    sent_invoice.refresh_from_db()
    assert sent_invoice.status == "SENT"


def test_removing_the_last_application_reopens_the_invoice(
    client, matter, sent_invoice
):
    payment = _payment(matter)
    application = PaymentApplication.objects.create(
        payment=payment, invoice=sent_invoice, amount_applied=Decimal("300.00")
    )

    client.delete(
        reverse("invoicing:payments-application-delete", args=[application.id])
    )

    sent_invoice.refresh_from_db()
    assert sent_invoice.status == "SENT"


def test_an_invoice_still_covered_by_other_money_stays_paid(
    client, matter, sent_invoice
):
    first, second = _payment(matter, "300.00"), _payment(matter, "50.00")
    PaymentApplication.objects.create(
        payment=first, invoice=sent_invoice, amount_applied=Decimal("300.00")
    )
    extra = PaymentApplication.objects.create(
        payment=second, invoice=sent_invoice, amount_applied=Decimal("0.00")
    )

    extra.delete()

    sent_invoice.refresh_from_db()
    assert sent_invoice.status == "PAID"


def test_a_paid_invoice_that_never_had_allocations_is_left_alone(matter, sent_invoice):
    """Invoices from before allocations existed are Paid with none."""
    Invoice.objects.filter(pk=sent_invoice.pk).update(status="PAID")
    sent_invoice.refresh_from_db()

    assert sent_invoice.amount_remaining == 0


def test_a_second_amount_for_the_same_invoice_adds_to_the_first(matter, sent_invoice):
    payment = _payment(matter)

    apply_to_invoice(
        PaymentApplication, "payment", payment, sent_invoice, Decimal("100.00")
    )
    apply_to_invoice(
        PaymentApplication, "payment", payment, sent_invoice, Decimal("200.00")
    )

    application = PaymentApplication.objects.get(payment=payment, invoice=sent_invoice)
    assert application.amount_applied == Decimal("300.00")
    sent_invoice.refresh_from_db()
    assert sent_invoice.status == "PAID"


@pytest.mark.parametrize(
    "name, make",
    [("invoicing:payments-delete", _payment), ("invoicing:credits-delete", _credit)],
)
def test_a_link_cannot_delete_money(client, matter, name, make):
    record = make(matter)

    assert client.get(reverse(name, args=[record.id])).status_code == 405
    assert type(record).objects.filter(pk=record.pk).exists()
    assert client.delete(reverse(name, args=[99999999])).status_code == 404


def test_a_link_cannot_delete_or_void_an_invoice(client, user, matter, sent_invoice):
    assert (
        client.get(
            reverse("invoicing:invoices-void", args=[sent_invoice.id])
        ).status_code
        == 405
    )
    draft = Invoice.objects.create(
        matter=matter, date_limit=date(2020, 1, 31), date_issued=date(2020, 2, 1)
    )
    assert (
        client.get(reverse("invoicing:invoices-delete", args=[draft.id])).status_code
        == 405
    )
    assert Invoice.objects.filter(pk=draft.pk).exists()

    assert (
        client.post(reverse("invoicing:invoices-delete", args=[draft.id])).status_code
        == 302
    )
    assert not Invoice.objects.filter(pk=draft.pk).exists()


def test_a_sent_invoice_cannot_be_edited_by_address(client, sent_invoice):
    url = reverse("invoicing:invoices-edit", args=[sent_invoice.id])

    assert client.get(url).status_code == 403
    assert client.post(url, {"discount": "50"}).status_code == 403


def test_trust_payment_is_refused_on_a_matter_with_no_client(
    client, matter, sent_invoice
):
    from apps.trust.models import Transaction

    matter.client = None
    matter.save()
    url = reverse("invoicing:quick-invoice-payment", args=[sent_invoice.id, "trust"])

    response = client.post(
        url,
        {
            "matter": matter.id,
            "date": "2020-02-05",
            "amount": "300.00",
            "payment_method": "TRUST",
            "detail": "Invoice",
        },
    )

    assert response.status_code == 204
    assert "no client" in response.headers.get("HX-Toast", "")
    assert not Transaction.objects.exists()
    assert not Payment.objects.exists()
