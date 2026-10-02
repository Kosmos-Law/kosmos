"""Safeguards around where money can go.

- ``PAYMENT_PROCESSOR=none`` switches online payment off: the emailed link
  still shows the invoice and its PDF, but nothing can be charged or recorded.
- A trust deposit must reach the trust account and nowhere else. An adapter
  that cannot guarantee that refuses the charge, staff are told before a
  request is sent, and a client who reaches the page sees a plain message
  instead of a server error.
"""

import json
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.invoicing.payments.models import Payment
from apps.invoicing.processors import (
    BANK,
    CARD,
    ChargeError,
    ProcessorConfigError,
    get_processor,
)
from apps.invoicing.processors.lawpay import LawPayProcessor
from apps.invoicing.processors.none import DisabledProcessor
from apps.invoicing.processors.stripe import StripeProcessor
from apps.invoicing.requests.models import PaymentRequest
from utils.signing import make_payment_token, make_request_token

pytestmark = pytest.mark.django_db


def _invoice_urls(invoice):
    token = make_payment_token(invoice)
    return (
        reverse("pay:invoice", kwargs={"token": token}),
        reverse("pay:charge", kwargs={"token": token}),
    )


# --- PAYMENT_PROCESSOR=none -------------------------------------------------


def test_factory_returns_the_disabled_processor():
    assert isinstance(get_processor("none"), DisabledProcessor)


def test_disabled_page_shows_the_invoice_but_no_payment_form(settings, sent_invoice):
    settings.PAYMENT_PROCESSOR = "none"
    page_url, _ = _invoice_urls(sent_invoice)

    response = Client().get(page_url)
    html = response.content.decode()

    assert response.status_code == 200
    assert "Online payment is not available" in html
    assert "payForm({" not in html
    # The link is still how the client gets the document.
    assert reverse("pay:invoice-pdf", kwargs={"token": page_url.split("/")[2]}) in html


def test_disabled_processor_charges_nothing(settings, sent_invoice):
    settings.PAYMENT_PROCESSOR = "none"
    _, charge_url = _invoice_urls(sent_invoice)

    response = Client().post(
        charge_url,
        data=json.dumps({"token": "anything", "method": CARD}),
        content_type="application/json",
    )

    assert response.status_code == 402
    assert response.json()["success"] is False
    assert Payment.objects.count() == 0
    sent_invoice.refresh_from_db()
    assert sent_invoice.amount_remaining > 0


def test_disabled_processor_refuses_directly():
    with pytest.raises(ChargeError):
        DisabledProcessor().charge(
            token="t", amount_cents=100, reference="r", method=CARD
        )


# --- LawPay: a trust charge must name the trust account ---------------------


def _lawpay(settings, **ids):
    settings.LAWPAY_SECRET_KEY = "sk_test"
    settings.LAWPAY_PUBLIC_KEY = "pk_test"
    settings.LAWPAY_OPERATING_CARD_ACCOUNT_ID = ids.get("operating_card", "")
    settings.LAWPAY_OPERATING_ECHECK_ACCOUNT_ID = ""
    settings.LAWPAY_TRUST_CARD_ACCOUNT_ID = ids.get("trust_card", "")
    settings.LAWPAY_TRUST_ECHECK_ACCOUNT_ID = ids.get("trust_echeck", "")
    return LawPayProcessor()


def test_lawpay_trust_charge_without_a_trust_account_is_refused(settings):
    processor = _lawpay(settings, operating_card="acct_operating")

    assert processor.trust_unavailable_reason()
    with pytest.raises(ProcessorConfigError, match="LAWPAY_TRUST_CARD_ACCOUNT_ID"):
        processor.account_id_for(method=CARD, trust=True)
    with pytest.raises(ProcessorConfigError, match="LAWPAY_TRUST_ECHECK_ACCOUNT_ID"):
        processor.account_id_for(method=BANK, trust=True)
    with pytest.raises(ProcessorConfigError):
        processor.client_config_for(amount_cents=100, reference="r", trust=True)


def test_lawpay_trust_charge_uses_the_trust_account_when_set(settings):
    processor = _lawpay(settings, trust_card="acct_trust")

    assert processor.trust_unavailable_reason() == ""
    assert processor.account_id_for(method=CARD, trust=True) == "acct_trust"


def test_lawpay_operating_charge_may_still_leave_the_account_to_the_gateway(settings):
    processor = _lawpay(settings)

    assert processor.account_id_for(method=CARD, trust=False) == ""


# --- Stripe: a single account, so no trust deposits -------------------------


def _stripe():
    return StripeProcessor(
        secret_key="sk_test_x", publishable_key="pk_test_x", webhook_secret="whsec_x"
    )


def test_stripe_refuses_trust_deposits():
    processor = _stripe()

    assert processor.trust_unavailable_reason()
    with pytest.raises(ProcessorConfigError):
        processor.client_config_for(amount_cents=100, reference="r", trust=True)
    with pytest.raises(ProcessorConfigError):
        processor.charge(
            token="pm_1", amount_cents=100, reference="r", method=CARD, trust=True
        )


def test_stripe_still_serves_operating_payments():
    config = _stripe().client_config_for(amount_cents=100, reference="r")

    assert config.processor == "stripe"


# --- What staff and clients see ---------------------------------------------


@pytest.fixture
def trust_request(contact):
    return PaymentRequest.objects.create(
        account="trust",
        client=contact,
        amount_requested=Decimal("500.00"),
        recipient_email="client@example.test",
        status="SENT",
    )


def _use_stripe(settings):
    settings.PAYMENT_PROCESSOR = "stripe"
    settings.STRIPE_SECRET_KEY = "sk_test_x"
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_x"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_x"


def test_client_sees_a_plain_message_when_the_deposit_cannot_be_routed(
    settings, trust_request
):
    _use_stripe(settings)
    url = reverse("pay:balance", kwargs={"token": make_request_token(trust_request)})

    response = Client().get(url)

    assert response.status_code == 503
    assert "Online payment is not available right now" in response.content.decode()


def test_client_sees_a_plain_message_when_the_processor_has_no_key(
    settings, sent_invoice
):
    settings.PAYMENT_PROCESSOR = "lawpay"
    settings.LAWPAY_SECRET_KEY = ""
    page_url, charge_url = _invoice_urls(sent_invoice)

    assert Client().get(page_url).status_code == 503
    response = Client().post(
        charge_url,
        data=json.dumps({"token": "t", "method": CARD}),
        content_type="application/json",
    )
    assert response.status_code == 503
    assert Payment.objects.count() == 0


def test_staff_cannot_send_a_trust_request_the_processor_cannot_route(
    settings, user, contact
):
    _use_stripe(settings)
    client = Client()
    client.login(username="Ollie", password="clawboy")
    client.get("/dash/")  # Set daily dash session to avoid redirect
    url = reverse("invoicing:requests-new-trust")

    form = client.get(url).content.decode()
    assert "Trust deposit requests cannot be sent" in form

    response = client.post(
        url,
        {"client": contact.id, "to": "client@example.test", "amount": "500"},
    )
    assert "Trust deposit requests cannot be sent" in response.content.decode()
    assert PaymentRequest.objects.count() == 0
