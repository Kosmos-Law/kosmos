"""What a client's link may reach. The pay pages take no login, only a
signed token, so each must refuse what the client was never sent."""

import json
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.invoicing.invoices.models import Invoice
from apps.invoicing.payments.models import Payment
from apps.invoicing.processors import CARD
from apps.invoicing.requests.models import PaymentRequest
from utils.signing import make_payment_token, make_request_token

pytestmark = pytest.mark.django_db


@pytest.fixture
def public_client():
    return Client()


@pytest.fixture
def balance_request(matter, sent_invoice):
    return PaymentRequest.objects.create(
        account="operating",
        matter=matter,
        amount_requested=Decimal("1000.00"),
        recipient_email="client@example.test",
        status="SENT",
    )


def _request_pdf(pay_request, invoice):
    return reverse(
        "pay:balance-invoice-pdf",
        kwargs={"token": make_request_token(pay_request), "invoice_id": invoice.id},
    )


@pytest.mark.parametrize("status", ["DRAFT", "APPROVED"])
def test_a_request_link_cannot_download_an_unsent_invoice(
    public_client, matter, balance_request, status
):
    unsent = Invoice.objects.create(
        matter=matter,
        date_limit=date(2020, 1, 31),
        date_issued=date(2020, 2, 1),
        status=status,
    )

    response = public_client.get(_request_pdf(balance_request, unsent))

    assert response.status_code == 404


@pytest.mark.parametrize("status", ["VOID", "UNCOLLECTIBLE"])
def test_a_closed_invoice_does_not_say_paid_in_full(
    public_client, sent_invoice, status
):
    Invoice.objects.filter(pk=sent_invoice.pk).update(status=status)
    sent_invoice.refresh_from_db()
    url = reverse("pay:invoice", kwargs={"token": make_payment_token(sent_invoice)})

    response = public_client.get(url)

    assert response.status_code == 410
    assert b"paid in full" not in response.content
    assert b"no longer open for payment" in response.content


def test_no_charge_is_taken_for_an_invoice_with_no_matter(public_client, sent_invoice):
    Invoice.objects.filter(pk=sent_invoice.pk).update(matter=None)
    sent_invoice.refresh_from_db()
    url = reverse("pay:charge", kwargs={"token": make_payment_token(sent_invoice)})

    response = public_client.post(
        url,
        data=json.dumps({"token": "fake-ok", "method": CARD}),
        content_type="application/json",
    )

    assert response.status_code == 409
    assert response.json()["success"] is False
    assert not Payment.objects.exists()
