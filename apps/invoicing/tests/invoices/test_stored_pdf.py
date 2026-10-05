"""When the stored invoice PDF is remade.

The stored copy is what the client's pay link serves, so it is remade when
the invoice is issued (a send out of Draft or Approved, like a status change
out of them) and when it is voided (stamped Void, with its entries still on
it). A resend keeps the copy the client already has."""

from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.activity.time.models import TimeEntry
from apps.invoicing.invoices.functions.send_invoice import (
    InvoiceSendError,
    send_invoice,
)
from apps.invoicing.invoices.models import Invoice
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db

_LOCAL_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@pytest.fixture
def offline_send(settings, tmp_path):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.STORAGES = _LOCAL_STORAGES
    settings.MEDIA_ROOT = str(tmp_path)
    Firm.objects.create(name="Example Law", email="firm@example.com")


def _with_stored_copy(invoice, status):
    invoice.status = status
    invoice.save()
    invoice.pdf_file.save("inv.pdf", ContentFile(b"%PDF-1.4 old copy"), save=True)
    return invoice


def _recording_store(calls):
    """A stand-in for store_invoice_pdf that notes the status the PDF would
    be rendered with and how many entries it would show."""

    def store(invoice, request=None, *, base_url=""):
        calls.append(
            (invoice.status, TimeEntry.objects.filter(invoice=invoice).count())
        )
        invoice.pdf_file.save("inv.pdf", ContentFile(b"%PDF-1.4 new copy"), save=False)
        Invoice.objects.filter(pk=invoice.pk).update(pdf_file=invoice.pdf_file)

    return store


@pytest.mark.parametrize("status", ["DRAFT", "APPROVED"])
def test_send_out_of_unsent_remakes_pdf_as_sent(invoice, offline_send, status):
    _with_stored_copy(invoice, status)
    calls = []
    with patch(
        "apps.invoicing.invoices.functions.send_invoice.store_invoice_pdf",
        _recording_store(calls),
    ):
        send_invoice(invoice, to="client@example.com")

    assert [status for status, _ in calls] == ["SENT"]
    invoice.refresh_from_db()
    assert invoice.status == "SENT"
    assert invoice.pdf_file.read() == b"%PDF-1.4 new copy"


def test_resend_keeps_the_stored_copy(invoice, offline_send):
    _with_stored_copy(invoice, "SENT")
    calls = []
    with patch(
        "apps.invoicing.invoices.functions.send_invoice.store_invoice_pdf",
        _recording_store(calls),
    ):
        send_invoice(invoice, to="client@example.com", attach_pdf=True)

    assert calls == []
    invoice.refresh_from_db()
    assert invoice.pdf_file.read() == b"%PDF-1.4 old copy"


def test_failed_send_leaves_status_unchanged(invoice, offline_send):
    _with_stored_copy(invoice, "DRAFT")
    with patch(
        "apps.invoicing.invoices.functions.send_invoice.store_invoice_pdf",
        side_effect=RuntimeError("no renderer"),
    ):
        with pytest.raises(InvoiceSendError, match="no renderer"):
            send_invoice(invoice, to="client@example.com")

    assert invoice.status == "DRAFT"
    invoice.refresh_from_db()
    assert invoice.status == "DRAFT"


def test_void_remakes_pdf_stamped_void_with_entries(
    client, user, matter, invoice, settings, tmp_path
):
    settings.STORAGES = _LOCAL_STORAGES
    settings.MEDIA_ROOT = str(tmp_path)
    _with_stored_copy(invoice, "SENT")
    TimeEntry.objects.create(
        user=user,
        matter=matter,
        date="2024-11-07",
        actions="Billable work",
        hours=1,
        rate=200,
        comp=False,
        entered=False,
        invoice=invoice,
    )
    on_invoice = TimeEntry.objects.filter(invoice=invoice).count()
    assert on_invoice == 2
    calls = []
    with patch(
        "apps.invoicing.invoices.views.store_invoice_pdf", _recording_store(calls)
    ):
        response = client.post(
            reverse("invoicing:invoices-void", kwargs={"pk": invoice.pk})
        )

    assert response.status_code == 204
    assert calls == [("VOID", on_invoice)]
    invoice.refresh_from_db()
    assert invoice.status == "VOID"
    assert TimeEntry.objects.filter(invoice=invoice).count() == 0
    assert invoice.pdf_file.read() == b"%PDF-1.4 new copy"
