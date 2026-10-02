"""Payments made from a client's trust funds.

A payment whose method is Trust is money moved out of the client's trust
account, so it always has one matching withdrawal on the trust ledger, and a
payment by any other method never has one. The payment and its withdrawal are
linked (``Transaction.payment``): changing the payment changes the
withdrawal, and deleting the payment deletes it.

Every place a payment is saved calls ``sync_trust_withdrawal`` afterwards, so
the rule does not depend on which screen recorded the payment.
"""

from decimal import Decimal

from apps.trust.models import Transaction
from apps.trust.trust import calculate_balance

TRUST_METHOD = "TRUST"


def trust_balance(client, excluding_payment=None):
    """What the client holds in trust: every deposit less every withdrawal,
    confirmed or not, as the ledger's Client Trust Balance (Pending) shows.

    ``excluding_payment`` leaves out that payment's own withdrawal, so an
    edit is checked against the balance as it stood before the payment."""
    transactions = Transaction.objects.filter(contact=client)
    if excluding_payment is not None and excluding_payment.pk:
        transactions = transactions.exclude(payment=excluding_payment)
    return Decimal(calculate_balance(transactions))


def sync_trust_withdrawal(payment):
    """Make the trust ledger agree with ``payment``. Returns the withdrawal,
    or None when the payment is not from trust."""
    existing = Transaction.objects.filter(payment=payment).first()

    if payment.payment_method != TRUST_METHOD:
        if existing:
            existing.delete()
        return None

    withdrawal = existing or Transaction(payment=payment, type="Withdrawal")
    withdrawal.contact = payment.matter.client
    withdrawal.date = payment.date
    withdrawal.amount = payment.amount
    withdrawal.description = payment.detail or f"Payment {payment.id}"
    withdrawal.save()
    return withdrawal
