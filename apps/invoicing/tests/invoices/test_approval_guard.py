"""A Draft invoice with time entries the AI logged (needs_approval) cannot
be approved or sent until a person has approved them: the status menu
refuses with a toast, the send service refuses before logging anything,
and the detail page says how many are waiting."""

import pytest
from django.urls import reverse

from apps.activity.time.models import TimeEntry
from apps.invoicing.invoices.functions.send_invoice import (
    InvoiceSendError,
    send_invoice,
)
from apps.invoicing.invoices.models import InvoiceTransmission

pytestmark = pytest.mark.django_db


@pytest.fixture
def flagged(user, matter):
    """An AI-logged entry inside the invoice's period; the draft's save
    pulls it onto the invoice."""
    return TimeEntry.objects.create(
        user=user,
        matter=matter,
        date="2024-12-02",
        actions="AI logged this",
        hours=0.3,
        rate=300,
        needs_approval=True,
    )


@pytest.fixture
def held_invoice(flagged, invoice):
    invoice.save()  # a draft's save gathers the period's unbilled entries
    flagged.refresh_from_db()
    assert flagged.invoice_id == invoice.id
    return invoice


def status_url(invoice, status):
    return reverse(
        "invoicing:invoices-edit-status",
        kwargs={"pk": invoice.id, "status": status, "view": "detail"},
    )


class TestStatusMenu:
    @pytest.mark.parametrize("status", ["APPROVED", "SENT", "DEFERRED"])
    def test_draft_is_held(self, client, held_invoice, status):
        response = client.post(status_url(held_invoice, status))
        assert response.status_code == 204
        assert "1 time entry that need" in response["HX-Toast"]
        held_invoice.refresh_from_db()
        assert held_invoice.status == "DRAFT"

    def test_released_once_approved(self, client, held_invoice, flagged):
        flagged.needs_approval = False
        flagged.save()
        client.post(status_url(held_invoice, "APPROVED"))
        held_invoice.refresh_from_db()
        assert held_invoice.status == "APPROVED"

    def test_plain_draft_is_not_held(self, client, invoice):
        client.post(status_url(invoice, "APPROVED"))
        invoice.refresh_from_db()
        assert invoice.status == "APPROVED"


class TestSending:
    def test_send_refuses_a_held_draft_without_logging(self, held_invoice, user):
        with pytest.raises(InvoiceSendError, match="need approval"):
            send_invoice(held_invoice, to="client@example.com", sent_by=user)
        held_invoice.refresh_from_db()
        assert held_invoice.status == "DRAFT"
        assert not InvoiceTransmission.objects.filter(invoice=held_invoice).exists()


class TestDetailPage:
    def test_shows_how_many_are_waiting(self, client, held_invoice):
        html = client.get(
            reverse("invoicing:invoices-detail", args=[held_invoice.id])
        ).content.decode()
        assert "1 time entry needs approval" in html
