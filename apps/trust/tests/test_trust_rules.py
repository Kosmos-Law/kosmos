"""The Trust summary's totals are the sum of the rows it shows; a client's
trust is counted once on the Work in Progress tab; and a transaction's
amount and type are checked before it is saved."""

from decimal import Decimal

import pytest

from apps.contacts.models import Contact
from apps.trust import trust
from apps.trust.forms import TransactionForm
from apps.trust.models import Transaction

pytestmark = pytest.mark.django_db


def _txn(contact, kind, amount, confirmed):
    return Transaction.objects.create(
        contact=contact,
        date="2024-01-02",
        type=kind,
        amount=Decimal(amount),
        confirmed=confirmed,
    )


def test_a_client_with_any_balance_is_listed_so_the_totals_add_up(user):
    """An unconfirmed deposit fully withdrawn by a confirmed withdrawal nets
    to zero on the asymmetric balance the list was built from, but leaves a
    confirmed balance of -500: the client was hidden while the total under
    the table still counted it."""
    client = Contact.objects.create(user=user, name="Elena Rivera")
    _txn(client, "Deposit", "500.00", confirmed=False)
    _txn(client, "Withdrawal", "500.00", confirmed=True)

    rows = trust.get_confirmed_client_balances(
        trust.get_pending_client_balances(trust.get_clients_asymmetric())
    )

    assert [row["id"] for row in rows] == [client.id]
    assert sum(row["confirmed_client_balance"] for row in rows) == (
        trust.get_confirmed_account_balance()
    )
    assert sum(row["pending_client_balance"] for row in rows) == (
        trust.get_pending_account_balance()
    )


def test_a_client_with_nothing_left_is_not_listed(user):
    client = Contact.objects.create(user=user, name="Elena Rivera")
    _txn(client, "Deposit", "500.00", confirmed=True)
    _txn(client, "Withdrawal", "500.00", confirmed=True)

    assert trust.get_clients_asymmetric() == []


@pytest.mark.parametrize("amount", ["0", "-25.00"])
def test_an_amount_must_be_more_than_zero(user, amount):
    client = Contact.objects.create(user=user, name="Elena Rivera")

    form = TransactionForm(
        {
            "contact": client.id,
            "date": "2024-01-02",
            "type": "Deposit",
            "method": "Check",
            "description": "Retainer",
            "amount": amount,
            "confirmed": "False",
        }
    )

    assert not form.is_valid()
    assert "amount" in form.errors


def test_the_type_is_a_deposit_or_a_withdrawal(user):
    client = Contact.objects.create(user=user, name="Elena Rivera")

    form = TransactionForm(
        {
            "contact": client.id,
            "date": "2024-01-02",
            "type": "Refund",
            "method": "Check",
            "description": "Retainer",
            "amount": "10.00",
            "confirmed": "False",
        }
    )

    assert not form.is_valid()
    assert "type" in form.errors
