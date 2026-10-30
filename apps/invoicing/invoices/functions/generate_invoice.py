import os
from tempfile import NamedTemporaryFile

from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import render_to_string

from apps.activity.expenses.models import ExpenseEntry
from apps.activity.flat_fees.models import FlatFeeEntry
from apps.activity.time.models import TimeEntry
from apps.invoicing.invoices.models import Invoice
from apps.management.pdf import pdf_html
from apps.settings.models import Firm
from apps.trust.trust import get_confirmed_client_balance


def generate_invoice(invoice: Invoice) -> NamedTemporaryFile:
    """Generate a PDF invoice for the given invoice instance."""

    if invoice.show_comp:
        time_entries = TimeEntry.objects.filter(
            invoice=invoice,
        ).order_by("date")
        expenses = ExpenseEntry.objects.filter(
            invoice=invoice,
        ).order_by("date")
        flat_fee_entries = FlatFeeEntry.objects.filter(
            invoice=invoice,
        ).order_by("date")
    else:
        time_entries = TimeEntry.objects.filter(
            invoice=invoice,
            comp=invoice.show_comp,
        ).order_by("date")
        expenses = ExpenseEntry.objects.filter(
            invoice=invoice,
            comp=invoice.show_comp,
        ).order_by("date")
        flat_fee_entries = FlatFeeEntry.objects.filter(
            invoice=invoice,
            comp=invoice.show_comp,
        ).order_by("date")

    # Get confirmed trust balance for the client
    confirmed_balance = 0
    if invoice.matter.client:
        confirmed_balance = get_confirmed_client_balance(invoice.matter.client.id)

    context = {
        "invoice": invoice,
        "time_entries": time_entries,
        "expenses": expenses,
        "flat_fee_entries": flat_fee_entries,
        "confirmed_balance": confirmed_balance,
        "company": Firm.objects.first(),
    }

    html_string = render_to_string("invoicing/invoices/invoice.html", context)
    html = pdf_html(html_string)

    with NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_file:
        html.write_pdf(target=pdf_file.name)
        pdf_file.seek(0)

    return pdf_file


def store_invoice_pdf(invoice: Invoice) -> None:
    """Generate PDF and store it in the invoice's pdf_file field."""
    pdf_file = generate_invoice(invoice)

    with open(pdf_file.name, "rb") as f:
        pdf_content = f.read()

    os.unlink(pdf_file.name)

    filename = f"invoice_{invoice.id}.pdf"

    if invoice.pdf_file:
        invoice.pdf_file.delete(save=False)

    invoice.pdf_file.save(filename, ContentFile(pdf_content), save=False)
    Invoice.objects.filter(pk=invoice.pk).update(pdf_file=invoice.pdf_file)


def refresh_invoice_pdf_later(invoice: Invoice) -> None:
    """Drop the invoice's stored PDF and queue a fresh one on the task
    worker, so a save or status change doesn't wait on WeasyPrint.

    Until the task runs, nothing serves the old copy: with no stored file
    the PDF views and the client's pay link render one on demand, and
    sending renders its own. A Draft gets no new copy: nothing serves a
    draft's stored PDF (the PDF views render drafts fresh, the pay link
    refuses them, and sending renders its own)."""
    if invoice.pdf_file:
        invoice.pdf_file.delete(save=False)
    Invoice.objects.filter(pk=invoice.pk).update(pdf_file=None)
    if invoice.status == "DRAFT":
        return

    from django_q.tasks import async_task

    transaction.on_commit(
        lambda: async_task(
            "apps.invoicing.invoices.functions.generate_invoice.store_missing_invoice_pdf",
            invoice.pk,
            task_name=f"invoice-pdf-{invoice.pk}",
            group="invoice_pdf",
        )
    )


def store_missing_invoice_pdf(invoice_id: int) -> None:
    """Task: store the invoice's PDF unless something already has (a send,
    or a client opening the link) or it has gone back to Draft."""
    invoice = Invoice.objects.filter(pk=invoice_id).first()
    if invoice is None or invoice.pdf_file or invoice.status == "DRAFT":
        return
    store_invoice_pdf(invoice)
