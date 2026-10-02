"""Payments made from a client's trust funds.

A payment by Trust is money leaving the client's trust account: it has one
matching withdrawal on the trust ledger, whichever screen recorded it, and
the two stay in step. A payment by any other method has none.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.activity.time.models import TimeEntry
from apps.contacts.models import Contact
from apps.invoicing.applications.models import PaymentApplication
from apps.invoicing.invoices.models import Invoice
from apps.invoicing.payments.models import Payment
from apps.trust.models import Transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_contact(user):
    return Contact.objects.create(user=user, name="Elena Rivera")


@pytest.fixture
def trust_matter(matter, client_contact):
    """The matter, with a client holding $1,000.00 in trust."""
    matter.client = client_contact
    matter.save()
    Transaction.objects.create(
        contact=client_contact,
        date=date(2020, 1, 2),
        type="Deposit",
        amount=Decimal("1000.00"),
        confirmed=True,
    )
    return matter


@pytest.fixture
def sent_invoice(user, trust_matter):
    """A Sent invoice for $300.00."""
    invoice = Invoice.objects.create(
        matter=trust_matter,
        date_limit=date(2020, 1, 31),
        date_issued=date(2020, 2, 1),
        status="SENT",
    )
    TimeEntry.objects.create(
        user=user,
        matter=trust_matter,
        date="2020-01-07",
        actions="Draft the complaint",
        hours=3,
        rate=100,
        invoice=invoice,
    )
    return invoice


def _post(matter, method="TRUST", amount="300.00", when="2020-02-05"):
    return {
        "matter": matter.id,
        "date": when,
        "payment_method": method,
        "amount": amount,
        "detail": "Invoice payment",
    }


def _withdrawals(contact):
    return Transaction.objects.filter(contact=contact, type="Withdrawal")


# --- the withdrawal follows the method ---------------------------------------


def test_a_trust_payment_on_the_payments_tab_records_its_withdrawal(
    client, trust_matter, client_contact
):
    response = client.post(reverse("invoicing:payments-add"), _post(trust_matter))

    assert response.status_code == 204
    payment = Payment.objects.get()
    withdrawal = _withdrawals(client_contact).get()
    assert withdrawal.payment == payment
    assert withdrawal.amount == Decimal("300.00")
    assert withdrawal.date == date(2020, 2, 5)


def test_a_payment_by_another_method_records_none(client, trust_matter, client_contact):
    client.post(reverse("invoicing:payments-add"), _post(trust_matter, method="CHECK"))

    assert Payment.objects.count() == 1
    assert not _withdrawals(client_contact).exists()


@pytest.mark.parametrize(
    "button, method, expected",
    [
        ("trust", "TRUST", 1),
        ("trust", "CHECK", 0),
        ("card", "TRUST", 1),
        ("card", "CARD", 0),
    ],
)
def test_on_an_invoice_the_method_decides_not_the_button(
    client, sent_invoice, trust_matter, client_contact, button, method, expected
):
    url = reverse("invoicing:quick-invoice-payment", args=[sent_invoice.id, button])

    client.post(url, _post(trust_matter, method=method))

    assert _withdrawals(client_contact).count() == expected
    sent_invoice.refresh_from_db()
    assert sent_invoice.status == "PAID"


def test_the_withdrawal_carries_the_payments_date(client, sent_invoice, trust_matter):
    url = reverse("invoicing:quick-invoice-payment", args=[sent_invoice.id, "trust"])

    client.post(url, _post(trust_matter, when="2020-02-20"))

    assert Transaction.objects.get(type="Withdrawal").date == date(2020, 2, 20)


def test_the_form_starts_at_what_is_still_owed(client, sent_invoice, trust_matter):
    payment = Payment.objects.create(
        matter=trust_matter,
        date=date(2020, 2, 2),
        amount=Decimal("100.00"),
        payment_method="CHECK",
    )
    PaymentApplication.objects.create(
        payment=payment, invoice=sent_invoice, amount_applied=Decimal("100.00")
    )
    url = reverse("invoicing:quick-invoice-payment", args=[sent_invoice.id, "trust"])

    form = client.get(url).context["form"]

    assert form.initial["amount"] == Decimal("200.00")
    assert list(form.fields["matter"].queryset) == [trust_matter]


# --- the client's balance -------------------------------------------------------


def test_a_trust_payment_larger_than_the_balance_is_refused(
    client, trust_matter, client_contact
):
    response = client.post(
        reverse("invoicing:payments-add"), _post(trust_matter, amount="1000.01")
    )

    assert response.status_code == 200
    assert "holds $1,000.00 in trust" in str(response.context["form"].errors)
    assert not Payment.objects.exists()
    assert not _withdrawals(client_contact).exists()


def test_the_whole_balance_can_be_paid(client, trust_matter, client_contact):
    response = client.post(
        reverse("invoicing:payments-add"), _post(trust_matter, amount="1000.00")
    )

    assert response.status_code == 204
    assert _withdrawals(client_contact).get().amount == Decimal("1000.00")


def test_a_trust_payment_needs_a_client(client, matter):
    response = client.post(reverse("invoicing:payments-add"), _post(matter))

    assert response.status_code == 200
    assert "no client" in str(response.context["form"].errors)
    assert not Payment.objects.exists()


def test_an_amount_must_be_more_than_zero(client, trust_matter):
    response = client.post(
        reverse("invoicing:payments-add"),
        _post(trust_matter, method="CHECK", amount="0"),
    )

    assert response.status_code == 200
    assert not Payment.objects.exists()


# --- editing and deleting ---------------------------------------------------------


@pytest.fixture
def trust_payment(client, trust_matter):
    client.post(reverse("invoicing:payments-add"), _post(trust_matter))
    return Payment.objects.get()


def test_editing_the_payment_changes_its_withdrawal(
    client, trust_payment, trust_matter, client_contact
):
    url = reverse("invoicing:payments-edit", args=[trust_payment.id])

    response = client.post(url, _post(trust_matter, amount="450.00", when="2020-03-01"))

    assert response.status_code == 204
    withdrawal = _withdrawals(client_contact).get()
    assert withdrawal.amount == Decimal("450.00")
    assert withdrawal.date == date(2020, 3, 1)


def test_an_edit_is_checked_against_the_balance_before_the_payment(
    client, trust_payment, trust_matter
):
    """The payment's own $300 is back in the balance while it is edited: it
    may be raised to the full $1,000, and not beyond."""
    url = reverse("invoicing:payments-edit", args=[trust_payment.id])

    assert client.post(url, _post(trust_matter, amount="1000.00")).status_code == 204
    assert client.post(url, _post(trust_matter, amount="1000.01")).status_code == 200


def test_changing_the_method_away_from_trust_removes_the_withdrawal(
    client, trust_payment, trust_matter, client_contact
):
    url = reverse("invoicing:payments-edit", args=[trust_payment.id])

    client.post(url, _post(trust_matter, method="CHECK"))

    assert not _withdrawals(client_contact).exists()


def test_deleting_the_payment_deletes_its_withdrawal(
    client, trust_payment, client_contact
):
    client.delete(reverse("invoicing:payments-delete", args=[trust_payment.id]))

    assert not Payment.objects.exists()
    assert not _withdrawals(client_contact).exists()


def test_a_withdrawal_entered_by_hand_is_not_touched(
    client, trust_payment, client_contact
):
    by_hand = Transaction.objects.create(
        contact=client_contact,
        date=date(2020, 2, 6),
        type="Withdrawal",
        amount=Decimal("50.00"),
        description="Filing fee advanced",
    )

    client.delete(reverse("invoicing:payments-delete", args=[trust_payment.id]))

    assert list(_withdrawals(client_contact)) == [by_hand]


def test_an_applied_payment_cannot_shrink_below_what_is_applied(
    client, sent_invoice, trust_matter
):
    client.post(
        reverse("invoicing:quick-invoice-payment", args=[sent_invoice.id, "card"]),
        _post(trust_matter, method="CHECK"),
    )
    payment = Payment.objects.get()
    url = reverse("invoicing:payments-edit", args=[payment.id])

    response = client.post(url, _post(trust_matter, method="CHECK", amount="299.99"))

    assert response.status_code == 200
    assert "applied to invoices" in str(response.context["form"].errors)
    payment.refresh_from_db()
    assert payment.amount == Decimal("300.00")


def test_an_applied_payment_cannot_move_to_another_matter(
    client, sent_invoice, trust_matter, practice_area
):
    from apps.matters.models import Matter

    client.post(
        reverse("invoicing:quick-invoice-payment", args=[sent_invoice.id, "card"]),
        _post(trust_matter, method="CHECK"),
    )
    payment = Payment.objects.get()
    other = Matter.objects.create(
        name="Another Matter", status="Open", practice_area=practice_area
    )
    Invoice.objects.create(
        matter=other,
        date_limit=date(2020, 1, 31),
        date_issued=date(2020, 2, 1),
        status="SENT",
    )
    url = reverse("invoicing:payments-edit", args=[payment.id])

    response = client.post(url, _post(other, method="CHECK"))

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.matter == trust_matter


# --- the withdrawal on the Trust tab ----------------------------------------------


def test_a_payments_withdrawal_cannot_be_edited_on_the_trust_tab(
    client, trust_payment, client_contact
):
    withdrawal = _withdrawals(client_contact).get()
    url = reverse("trust:edit", args=[withdrawal.id])

    opened = client.get(url)
    saved = client.post(
        url,
        {
            "contact": client_contact.id,
            "date": "2020-02-05",
            "type": "Withdrawal",
            "amount": "5.00",
            "description": "Changed",
        },
    )

    assert opened.status_code == saved.status_code == 204
    assert "payment from trust" in opened["HX-Toast"]
    withdrawal.refresh_from_db()
    assert withdrawal.amount == Decimal("300.00")


def test_a_payments_withdrawal_cannot_be_deleted_on_the_trust_tab(
    client, trust_payment, client_contact
):
    withdrawal = _withdrawals(client_contact).get()

    response = client.delete(reverse("trust:delete", args=[withdrawal.id]))

    assert response.status_code == 204
    assert "payment from trust" in response["HX-Toast"]
    assert _withdrawals(client_contact).count() == 1


def test_a_payments_withdrawal_can_still_be_confirmed(
    client, trust_payment, client_contact
):
    withdrawal = _withdrawals(client_contact).get()

    client.post(reverse("trust:confirmed", args=[withdrawal.id]))

    withdrawal.refresh_from_db()
    assert withdrawal.confirmed


def test_deleting_the_matter_leaves_the_withdrawal_on_the_trust_ledger(
    client, trust_payment, trust_matter, client_contact
):
    """The money left the trust account whatever became of the matter's
    records: a trust ledger row never disappears as a side effect."""
    trust_matter.delete()

    assert not Payment.objects.exists()
    withdrawal = _withdrawals(client_contact).get()
    assert withdrawal.payment is None
    assert withdrawal.amount == Decimal("300.00")
