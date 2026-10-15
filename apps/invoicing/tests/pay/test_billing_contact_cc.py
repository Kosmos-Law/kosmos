"""The matter's billing contacts pre-fill the Cc of every billing email's
modal: send invoice, payment reminder, request payment (on matter change),
resend request and request reminder. The person sending can still change
it; a trust deposit request has no matter and so no billing contacts."""

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.contacts.models import Contact
from apps.invoicing.requests.models import PaymentRequest

pytestmark = pytest.mark.django_db

CC = "greg@example.test, jeremy@example.test"


@pytest.fixture
def staff(user):
    client = Client()
    client.force_login(user)
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


@pytest.fixture
def billed_matter(user, matter):
    matter.client = Contact.objects.create(
        user=user, name="Roger Client", email="roger@example.test"
    )
    matter.save()
    matter.billing_contacts.set(
        [
            Contact.objects.create(
                user=user, name="Jeremy Henderson", email="jeremy@example.test"
            ),
            Contact.objects.create(
                user=user, name="Greg Horner", email="greg@example.test"
            ),
        ]
    )
    return matter


@pytest.fixture
def operating_request(billed_matter):
    return PaymentRequest.objects.create(
        matter=billed_matter,
        amount_requested=Decimal("100.00"),
        recipient_email="roger@example.test",
        status="SENT",
    )


def cc_value(page):
    """The Cc input's value attribute on a modal page."""
    start = page.index('name="cc"')
    value_at = page.index('value="', start) + len('value="')
    return page[value_at : page.index('"', value_at)]


def test_send_invoice_modal_copies_the_billing_contacts(
    staff, billed_matter, sent_invoice
):
    page = staff.get(
        reverse("invoicing:invoices-send", kwargs={"pk": sent_invoice.id})
    ).content.decode()
    assert cc_value(page) == CC
    assert 'value="roger@example.test"' in page  # the client stays the To


def test_reminder_modal_copies_the_billing_contacts(staff, billed_matter, sent_invoice):
    page = staff.get(
        reverse("invoicing:invoices-send-reminder", kwargs={"pk": sent_invoice.id})
    ).content.decode()
    assert cc_value(page) == CC


def test_send_invoice_modal_cc_is_blank_without_billing_contacts(staff, sent_invoice):
    page = staff.get(
        reverse("invoicing:invoices-send", kwargs={"pk": sent_invoice.id})
    ).content.decode()
    assert cc_value(page) == ""


def test_choosing_a_matter_fills_the_request_cc(staff, billed_matter, sent_invoice):
    page = staff.get(
        reverse("invoicing:requests-matter-fields"), {"matter": billed_matter.id}
    ).content.decode()
    assert cc_value(page) == CC
    # Swapped out-of-band into the open modal, next to the To and Amount.
    assert 'id="request-cc"' in page
    assert page.count('hx-swap-oob="true"') == 2


def test_resend_and_reminder_modals_copy_the_billing_contacts(staff, operating_request):
    for name in ("invoicing:requests-resend", "invoicing:requests-send-reminder"):
        page = staff.get(
            reverse(name, kwargs={"pk": operating_request.id})
        ).content.decode()
        assert cc_value(page) == CC, name
