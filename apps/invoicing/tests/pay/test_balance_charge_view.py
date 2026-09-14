"""End-to-end tests for the public ``balance_charge`` view (the "pay account
balance" / catch-up flow used by PaymentRequest links).

Mirrors test_pay_charge_view.py — everything charged through FakeProcessor.
"""

import json
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.invoicing.payments.models import Payment
from apps.invoicing.processors import CARD
from apps.invoicing.requests.models import PaymentRequest
from utils.signing import make_request_token

pytestmark = pytest.mark.django_db


@pytest.fixture
def public_client():
    return Client()


@pytest.fixture
def balance_request(matter, sent_invoice):
    """An operating-account catch-up request for the matter's open balance."""
    return PaymentRequest.objects.create(
        account="operating",
        matter=matter,
        amount_requested=Decimal("1000.00"),
        recipient_email="client@example.test",
        status="SENT",
    )


def _charge_url(pay_request):
    return reverse(
        "pay:balance-charge", kwargs={"token": make_request_token(pay_request)}
    )


def _post_charge(client, pay_request, *, token="fake-ok", method=CARD):
    url = _charge_url(pay_request)
    body = {"token": token, "method": method}
    return client.post(url, data=json.dumps(body), content_type="application/json")


def test_card_charge_records_payment_and_settles_request(
    public_client, balance_request, sent_invoice
):
    response = _post_charge(public_client, balance_request, method=CARD)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    payment = Payment.objects.get(processor="fake")
    assert payment.amount == Decimal("1000.00")

    balance_request.refresh_from_db()
    assert balance_request.status == "PAID"
    assert balance_request.payment_id == payment.pk


def test_soft_decline_returns_402_and_leaves_request_sent(
    public_client, balance_request
):
    """Regression: a processor can return a transaction that just isn't
    accepted (Confido: status_v2 ERROR) instead of raising at the GraphQL
    layer. The view used to fall through to `success: true` in this case —
    the client saw "payment successful" while nothing was recorded and the
    request stayed unpaid."""
    response = _post_charge(public_client, balance_request, token="fake-soft-decline")
    assert response.status_code == 402
    assert response.json()["success"] is False

    assert not Payment.objects.exists()
    balance_request.refresh_from_db()
    assert balance_request.status == "SENT"
    assert balance_request.payment_id is None


def test_hard_decline_returns_402_and_leaves_request_sent(
    public_client, balance_request
):
    response = _post_charge(public_client, balance_request, token="fake-decline")
    assert response.status_code == 402
    assert response.json()["success"] is False

    assert not Payment.objects.exists()
    balance_request.refresh_from_db()
    assert balance_request.status == "SENT"
