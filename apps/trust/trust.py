from datetime import timedelta
from decimal import Decimal

from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.contacts.models import Contact
from apps.trust.models import Transaction


def calculate_balance(transactions):
    bal = 0
    for transaction in transactions:
        if transaction.type == "Deposit":
            bal += transaction.amount
        elif transaction.type == "Withdrawal":
            bal -= transaction.amount
    return bal


def get_pending_client_balance(contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    transactions = Transaction.objects.filter(contact=contact)
    balance = calculate_balance(transactions)
    return balance


def get_confirmed_client_balance(contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    transactions = Transaction.objects.filter(contact=contact, confirmed=True)
    balance = calculate_balance(transactions)
    return balance


def get_asymmetric_client_balance(contact_id):
    """Get all entries in the trust table for a given contact.

    Params:
    contact_id(int): the id for a contact

    Returns:
    balance (int): the trust balance for the given client

    Notes:
    The balance includes (a) all deposits regardless of whether they are confirmed, but
    (b) only confirmed withdrawals

    This function is used in connection with get_clients_asymmetric.
    It helps to identify all cients with a pending trust balance greater than $0.
    This makes sure that new clients are included in the 'Account Summary' page.

    """

    contact = get_object_or_404(Contact, pk=contact_id)
    deposits = Transaction.objects.filter(contact=contact, type="Deposit")
    withdrawals = Transaction.objects.filter(
        contact=contact, type="Withdrawal", confirmed=True
    )

    total_deposits = calculate_balance(deposits)
    total_withdrawals = -1 * calculate_balance(withdrawals)  # note the negative
    balance = total_deposits - total_withdrawals
    return balance


def get_pending_client_balances(contacts):
    if contacts:
        for contact in contacts:
            contact["pending_client_balance"] = get_pending_client_balance(
                contact["id"]
            )
    return contacts


def get_confirmed_client_balances(contacts):
    if contacts:
        for contact in contacts:
            contact["confirmed_client_balance"] = get_confirmed_client_balance(
                contact["id"]
            )
    return contacts


def get_clients_asymmetric():
    """Get all contacts for which there is an entry in the trust table.

    Returns:
    current_contacts (list): Dicts with contact id, name, and balance

    """

    # The three balances of every client in one query: the asymmetric one
    # (all deposits, confirmed withdrawals only, as get_asymmetric_client_balance
    # has it), the pending one (every row) and the confirmed one (confirmed
    # rows), each a signed sum of deposits less withdrawals.
    deposit = When(type="Deposit", then=F("amount"))
    withdrawal = When(type="Withdrawal", then=-F("amount"))
    zero = Value(Decimal("0"))
    money = DecimalField(max_digits=9, decimal_places=2)
    rows = (
        Transaction.objects.exclude(contact=None)
        .values("contact_id", "contact__name")
        .annotate(
            asymmetric=Sum(
                Case(
                    deposit,
                    When(type="Withdrawal", confirmed=True, then=-F("amount")),
                    default=zero,
                    output_field=money,
                )
            ),
            pending=Sum(Case(deposit, withdrawal, default=zero, output_field=money)),
            confirmed=Sum(
                Case(deposit, withdrawal, default=zero, output_field=money),
                filter=Q(confirmed=True),
            ),
        )
    )

    # Listed when any of the client's balances is not zero. (Listing on
    # the asymmetric balance alone hid a client whose pending or
    # confirmed balance was still non-zero, while the totals under the
    # table, which add up every transaction, went on counting them.)
    current_contacts = [
        {
            "id": row["contact_id"],
            "name": row["contact__name"],
            "bal": row["asymmetric"] or 0,
        }
        for row in rows
        if (row["asymmetric"] or 0) != 0
        or (row["pending"] or 0) != 0
        or (row["confirmed"] or 0) != 0
    ]

    # sort the list of dicts by the 'name' of each dict
    return sorted(current_contacts, key=lambda k: k["name"])


def get_pending_account_balance():
    transactions = Transaction.objects.all()
    balance = calculate_balance(transactions)
    return balance


def get_confirmed_account_balance():
    transactions = Transaction.objects.filter(confirmed=True)
    balance = calculate_balance(transactions)
    return balance


def get_client_history(contact_id):
    contact = get_object_or_404(Contact, pk=contact_id)
    transactions = Transaction.objects.filter(contact=contact).order_by("date", "id")
    return transactions


def get_account_history(interval):
    today = timezone.localdate()
    thirty_days = today - timedelta(days=30)
    sixty_days = today - timedelta(days=60)

    if interval == "all":
        transactions = Transaction.objects.all()
    elif interval == "60days":
        transactions = Transaction.objects.filter(date__gt=sixty_days)
    else:
        transactions = Transaction.objects.filter(date__gt=thirty_days)
    transactions = transactions.order_by("-date", "-id")

    return transactions
