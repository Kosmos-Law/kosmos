"""get_clients_asymmetric() lists every client with trust activity in a
fixed number of queries, whatever the number of clients, and agrees with
the per-client balance functions on every figure."""

from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.contacts.models import Contact
from apps.trust.models import Transaction
from apps.trust.trust import (
    get_asymmetric_client_balance,
    get_clients_asymmetric,
    get_confirmed_client_balance,
    get_pending_client_balance,
)

pytestmark = pytest.mark.django_db


def _ledger(contact, rows):
    for kind, amount, confirmed in rows:
        Transaction.objects.create(
            contact=contact,
            date="2024-01-01",
            type=kind,
            amount=Decimal(amount),
            confirmed=confirmed,
        )


@pytest.fixture
def clients(user, folder):
    """Six clients whose balances exercise every listing rule."""
    specs = {
        # Only an unconfirmed deposit: listed on the pending balance.
        "Pending Only": [("Deposit", "100.00", False)],
        # Deposit and withdrawal both confirmed and equal: not listed.
        "Settled": [("Deposit", "100.00", True), ("Withdrawal", "100.00", True)],
        # Unconfirmed withdrawal: the asymmetric balance ignores it, the
        # pending balance does not.
        "Pending Withdrawal": [
            ("Deposit", "100.00", True),
            ("Withdrawal", "100.00", False),
        ],
        # Confirmed withdrawal against an unconfirmed deposit: the confirmed
        # balance is negative while the asymmetric one is zero.
        "Confirmed Short": [
            ("Deposit", "100.00", False),
            ("Withdrawal", "100.00", True),
        ],
        # A mixed ledger with money left.
        "Active": [
            ("Deposit", "500.00", True),
            ("Deposit", "250.00", False),
            ("Withdrawal", "125.00", True),
            ("Withdrawal", "25.00", False),
        ],
        # A row of no type counts for nothing.
        "Untyped": [(None, "40.00", True)],
    }
    made = {}
    for name, rows in specs.items():
        contact = Contact.objects.create(user=user, folder=folder, name=name)
        _ledger(contact, rows)
        made[name] = contact
    return made


def test_agrees_with_the_per_client_balances(clients):
    result = {row["name"]: row for row in get_clients_asymmetric()}

    assert sorted(result) == [
        "Active",
        "Confirmed Short",
        "Pending Only",
        "Pending Withdrawal",
    ]
    for name, row in result.items():
        contact = clients[name]
        assert row["id"] == contact.id
        assert row["bal"] == get_asymmetric_client_balance(contact.id)
    assert result["Active"]["bal"] == Decimal("625.00")
    assert result["Confirmed Short"]["bal"] == 0
    assert get_pending_client_balance(clients["Pending Withdrawal"].id) == 0
    assert get_confirmed_client_balance(clients["Confirmed Short"].id) == Decimal(
        "-100.00"
    )


def test_sorted_by_name(clients):
    names = [row["name"] for row in get_clients_asymmetric()]
    assert names == sorted(names)


def test_query_count_does_not_grow_with_clients(user, folder, clients):
    with CaptureQueriesContext(connection) as before:
        get_clients_asymmetric()

    for n in range(10):
        contact = Contact.objects.create(user=user, folder=folder, name=f"More {n}")
        _ledger(contact, [("Deposit", "10.00", False)])

    with CaptureQueriesContext(connection) as after:
        assert len(get_clients_asymmetric()) == 14

    assert len(after) == len(before)
    assert len(after) <= 2
