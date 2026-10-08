"""With online payment off (``PAYMENT_PROCESSOR=none``) nothing offers or
promises it.

- Invoice emails and reminders drop "Pay now" / "Pay online". They keep a
  "View invoice" link, because the page behind it is also where the client
  downloads the PDF.
- Payment and trust deposit requests cannot be created, resent or reminded,
  and the actions that start them are hidden.
- The Requests sub-tab shows only while there are requests to look back on.

With any other processor (the pinned ``fake`` here) everything stays as it was.
"""

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.invoicing.invoices.functions.send_invoice import send_invoice, send_reminder
from apps.invoicing.processors import online_payments_enabled
from apps.invoicing.requests.models import PaymentRequest
from apps.invoicing.requests.send import (
    PaymentRequestSendError,
    send_payment_request,
    send_request_reminder,
)

pytestmark = pytest.mark.django_db

OFF_MESSAGE = "Online payments are not set up."


@pytest.fixture
def staff(user):
    client = Client()
    client.force_login(user)
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


@pytest.fixture
def locmem_email(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture
def operating_request(matter):
    return PaymentRequest.objects.create(
        matter=matter,
        amount_requested=Decimal("100.00"),
        recipient_email="client@example.test",
        status="SENT",
    )


@pytest.mark.parametrize(
    "name,enabled",
    [("none", False), ("fake", True), ("lawpay", True), ("stripe", True)],
)
def test_online_payments_enabled(settings, name, enabled):
    settings.PAYMENT_PROCESSOR = name
    assert online_payments_enabled() is enabled


# --- Invoice emails ---------------------------------------------------------


@pytest.mark.parametrize("send", [send_invoice, send_reminder])
def test_invoice_emails_offer_payment_when_on(
    settings, locmem_email, mailoutbox, sent_invoice, send
):
    send(sent_invoice, to="client@example.test")

    msg = mailoutbox[0]
    html = msg.alternatives[0][0]
    assert "Pay now" in html
    assert "Pay online:" in msg.body
    assert "/pay/" in msg.body


@pytest.mark.parametrize("send", [send_invoice, send_reminder])
def test_invoice_emails_only_link_the_invoice_when_off(
    settings, locmem_email, mailoutbox, sent_invoice, send
):
    settings.PAYMENT_PROCESSOR = "none"

    send(sent_invoice, to="client@example.test")

    msg = mailoutbox[0]
    html = msg.alternatives[0][0]
    for text in (html, msg.body):
        assert "Pay now" not in text
        assert "Pay online" not in text
        assert "and pay it" not in text
    assert "View invoice" in html
    # The page still serves the PDF, so the link stays.
    assert "/pay/" in msg.body


# --- Request sending --------------------------------------------------------


def test_request_emails_refused_when_off(
    settings, locmem_email, mailoutbox, operating_request
):
    settings.PAYMENT_PROCESSOR = "none"

    with pytest.raises(PaymentRequestSendError, match=OFF_MESSAGE):
        send_payment_request(operating_request, to="client@example.test")
    with pytest.raises(PaymentRequestSendError, match=OFF_MESSAGE):
        send_request_reminder(operating_request, to="client@example.test")
    assert mailoutbox == []


def test_request_payment_endpoint_refuses_when_off(
    settings, locmem_email, mailoutbox, staff, matter, sent_invoice
):
    settings.PAYMENT_PROCESSOR = "none"
    url = reverse("invoicing:requests-new")

    form = staff.get(url).content.decode()
    assert OFF_MESSAGE in form
    assert "PAYMENT_PROCESSOR" not in form

    response = staff.post(url, {"matter": matter.id, "to": "client@example.test"})
    assert response.status_code == 200
    assert OFF_MESSAGE in response.content.decode()
    assert PaymentRequest.objects.count() == 0
    assert mailoutbox == []


def test_request_payment_endpoint_still_sends_when_on(
    locmem_email, mailoutbox, staff, matter, sent_invoice
):
    response = staff.post(
        reverse("invoicing:requests-new"),
        {"matter": matter.id, "to": "client@example.test"},
    )

    assert response.status_code == 204
    assert PaymentRequest.objects.count() == 1
    assert "Pay now" in mailoutbox[0].alternatives[0][0]


def test_trust_request_endpoint_refuses_when_off(
    settings, locmem_email, mailoutbox, staff, contact
):
    settings.PAYMENT_PROCESSOR = "none"
    url = reverse("invoicing:requests-new-trust")

    form = staff.get(url).content.decode()
    assert OFF_MESSAGE in form
    assert "PAYMENT_PROCESSOR" not in form

    response = staff.post(
        url, {"client": contact.id, "to": "client@example.test", "amount": "500"}
    )
    assert OFF_MESSAGE in response.content.decode()
    assert PaymentRequest.objects.count() == 0
    assert mailoutbox == []


@pytest.mark.parametrize(
    "route", ["invoicing:requests-resend", "invoicing:requests-send-reminder"]
)
def test_resend_and_reminder_refuse_when_off(
    settings, locmem_email, mailoutbox, staff, operating_request, route
):
    settings.PAYMENT_PROCESSOR = "none"
    url = reverse(route, args=[operating_request.id])

    assert OFF_MESSAGE in staff.get(url).content.decode()
    response = staff.post(url, {"to": "client@example.test"})
    assert OFF_MESSAGE in response.content.decode()
    assert mailoutbox == []
    assert not operating_request.transmissions.exists()


# --- What staff see ---------------------------------------------------------


def test_request_actions_shown_when_on(staff, operating_request):
    requests_page = staff.get(reverse("invoicing:requests-index")).content.decode()
    trust_page = staff.get(reverse("trust:index")).content.decode()

    assert "Request Payment" in requests_page
    assert "Request Trust Deposit" in requests_page
    assert reverse("invoicing:requests-resend", args=[operating_request.id]) in (
        requests_page
    )
    assert "Request Deposit" in trust_page
    assert reverse("invoicing:requests-index") in trust_page  # sub-nav tab


def test_request_actions_hidden_when_off(settings, staff, operating_request):
    settings.PAYMENT_PROCESSOR = "none"

    requests_page = staff.get(reverse("invoicing:requests-index")).content.decode()
    trust_page = staff.get(reverse("trust:index")).content.decode()

    assert "Request Payment" not in requests_page
    assert "Request Trust Deposit" not in requests_page
    assert reverse("invoicing:requests-resend", args=[operating_request.id]) not in (
        requests_page
    )
    # Cancel stays, so an old request can still be closed out.
    assert reverse("invoicing:requests-cancel", args=[operating_request.id]) in (
        requests_page
    )
    assert "Request Deposit" not in trust_page
    # Existing requests keep the sub-nav tab.
    assert reverse("invoicing:requests-index") in trust_page


def test_requests_tab_hidden_when_off_with_no_requests(settings, staff):
    settings.PAYMENT_PROCESSOR = "none"

    trust_page = staff.get(reverse("trust:index")).content.decode()

    assert reverse("invoicing:requests-index") not in trust_page


# --- The client's page for an old link -------------------------------------


def test_old_request_link_shows_the_balance_without_a_payment_promise(
    settings, operating_request, sent_invoice
):
    from utils.signing import make_request_token

    settings.PAYMENT_PROCESSOR = "none"
    url = reverse(
        "pay:balance", kwargs={"token": make_request_token(operating_request)}
    )

    html = Client().get(url).content.decode()

    assert "Online payment is not available" in html
    assert "Pay Account Balance" not in html
    assert "payForm({" not in html
