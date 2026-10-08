"""Email an invoice PDF to the client and record the transmission.

Replaces the manual LawPay "QuickBill" send. On success the invoice is marked
SENT (with date_sent) and a 'sent' InvoiceTransmission row is written; on failure
a 'failed' row is logged and InvoiceSendError is raised with the status left
unchanged.
"""

from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.utils import timezone

from apps.invoicing.invoices.functions.generate_invoice import store_invoice_pdf
from apps.invoicing.invoices.models import UNSENT_STATUSES, InvoiceTransmission
from apps.invoicing.pay.links import payment_url
from apps.invoicing.processors import online_payments_enabled
from apps.settings.models import Firm
from utils.mail import (
    FIRM_LOGO_CID,
    attach_firm_logo,
    billing_from_email,
    billing_reply_to,
    firm_postal_address,
    render_inlined,
)


class InvoiceSendError(Exception):
    """Raised when an invoice could not be emailed (recipient missing, SMTP
    failure, PDF generation error). The invoice status is left unchanged."""


def _parse_recipients(raw):
    """Split a comma/semicolon-separated address string into a clean list."""
    if not raw:
        return []
    return [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]


def _invalid_addresses(addresses):
    """Return the subset of `addresses` that aren't valid email addresses."""
    invalid = []
    for addr in addresses:
        try:
            validate_email(addr)
        except ValidationError:
            invalid.append(addr)
    return invalid


def _invoice_links(invoice, request):
    """The email's link to the invoice page, as `pay_url` (a "Pay now" button)
    when online payment is on, or `view_url` ("View invoice") when it is off.
    The page is also where the client downloads the PDF, so the link stays
    either way; only the promise of online payment goes."""
    url = payment_url(invoice, request)
    if online_payments_enabled():
        return {"pay_url": url, "view_url": ""}
    return {"pay_url": "", "view_url": url}


def _log(
    invoice, *, to_email, cc_email, sent_by, status, error="", when=None, kind="invoice"
):
    InvoiceTransmission.objects.create(
        invoice=invoice,
        kind=kind,
        sent_at=when or timezone.now(),
        to_email=to_email or "",
        cc_email=cc_email or "",
        sent_by=sent_by,
        status=status,
        error=error or "",
    )


def _store_pdf_as_sent(invoice, request):
    """Store the PDF as the client will see it: the watermark follows the
    status at render time, and the status is only saved once the email has
    gone out."""
    status = invoice.status
    invoice.status = "SENT"
    try:
        store_invoice_pdf(invoice, request)
    finally:
        invoice.status = status


def send_invoice(
    invoice,
    *,
    to=None,
    cc=None,
    message=None,
    attach_pdf=False,
    sent_by=None,
    request=None,
):
    """Send `invoice` to the client. Returns True on success.

    to / cc: override recipient(s); each may be a comma-separated list of
    addresses. The default recipient is the matter client's email.
    message: cover-note override; defaults to the invoice's own `message`.
    attach_pdf: also attach the invoice PDF. Off by default — the PDF is
    always downloadable behind the tokenized pay link, and attachment-free
    email clears spam filters more reliably.
    """
    matter = invoice.matter
    client = matter.client if matter else None
    to_list = _parse_recipients(to)
    if not to_list and client and client.email:
        to_list = [client.email.strip()]
    cc_list = _parse_recipients(cc)
    to_joined = ", ".join(to_list)
    cc_joined = ", ".join(cc_list)

    if not to_list:
        _log(
            invoice,
            to_email="",
            cc_email=cc_joined,
            sent_by=sent_by,
            status="failed",
            error="No client email address on file.",
        )
        raise InvoiceSendError("This matter's client has no email address on file.")

    invalid = _invalid_addresses(to_list + cc_list)
    if invalid:
        error = f"Invalid email address(es): {', '.join(invalid)}"
        _log(
            invoice,
            to_email=to_joined,
            cc_email=cc_joined,
            sent_by=sent_by,
            status="failed",
            error=error,
        )
        raise InvoiceSendError(error)

    try:
        # A send that issues the invoice remakes its PDF, as a status change
        # out of Draft or Approved does: the copy stored while it was a draft
        # carries the DRAFT watermark, and an approved invoice's entries can
        # change after its copy was made. A resend keeps the copy the client
        # already has (it is only made if somehow missing), rather than
        # paying the WeasyPrint cost on every send.
        if invoice.status in UNSENT_STATUSES:
            _store_pdf_as_sent(invoice, request)
        elif attach_pdf and not invoice.pdf_file:
            store_invoice_pdf(invoice, request)

        cover = message if message is not None else (invoice.message or "")
        # Firm branding comes from the Firm settings record (same source as
        # the PDF), not a hardcoded setting.
        company = Firm.objects.first()
        bcc_list = _parse_recipients(company.invoice_bcc) if company else []
        # Billing correspondence (client replies + the "contact us" address in
        # the email body) goes to the firm's billing email, falling back to the
        # general firm email when no billing address is configured.
        billing_email = ""
        if company:
            billing_email = company.billing_email or company.email
        context = {
            "invoice": invoice,
            "matter_name": matter.name if matter else "",
            "matter_number": matter.id if matter else "",
            "client_name": client.name if client else "",
            "amount_due": invoice.amount_remaining,
            "cover_message": cover,
            "firm_name": company.name if company else "",
            "billing_email": billing_email,
            # Tokenized link to the invoice page. With online payment off it
            # still serves the PDF, so the email offers it as "View invoice".
            **_invoice_links(invoice, request),
            "attach_pdf": attach_pdf,
            "logo_cid": FIRM_LOGO_CID if company and company.email_logo else "",
            "firm_address": firm_postal_address(company),
        }
        # Client-facing: lead with the firm name, then the invoice number —
        # matter identifiers are internal and stay out of client emails.
        firm = company.name if company else ""
        subject = f"{firm} - " if firm else ""
        subject += f"Invoice {invoice.id}"

        email = EmailMultiAlternatives(
            subject=subject,
            body=render_to_string("emails/invoice_email.txt", context),
            from_email=billing_from_email(company),  # "<Firm>" <billing addr>
            to=to_list,
            cc=cc_list,
            # Firm archive copy (Firm.invoice_bcc); the BCC'd mailbox retains
            # the full email, cover message and PDF included.
            bcc=bcc_list or None,
            # Client replies go to the firm's billing email (Firm settings),
            # labeled "<Firm> Billing", not the unattended From address.
            reply_to=[billing_reply_to(company)] if billing_email else None,
        )
        email.attach_alternative(
            render_inlined("emails/invoice_email.html", context), "text/html"
        )
        if attach_pdf:
            with invoice.pdf_file.open("rb") as f:
                email.attach(f"invoice_{invoice.id}.pdf", f.read(), "application/pdf")
        # After the PDF: with a document attached the root must stay mixed
        # (attach_firm_logo only switches to related when attachments is empty).
        if context["logo_cid"]:
            attach_firm_logo(email, company)
        email.send()
    except Exception as exc:
        _log(
            invoice,
            to_email=to_joined,
            cc_email=cc_joined,
            sent_by=sent_by,
            status="failed",
            error=str(exc),
        )
        raise InvoiceSendError(f"Could not send the invoice: {exc}") from exc

    now = timezone.now()
    invoice.status = "SENT"
    invoice.date_sent = now
    invoice.save(update_fields=["status", "date_sent"])
    _log(
        invoice,
        to_email=to_joined,
        cc_email=cc_joined,
        sent_by=sent_by,
        status="sent",
        when=now,
    )
    return True


def days_since_sent(invoice):
    """Whole days since the invoice PDF was last actually delivered — a direct
    send or a payment request that attached it (falling back to date_sent).
    Reminders don't reset the clock. None when it was never emailed."""
    last = (
        invoice.transmissions.filter(kind__in=["invoice", "request"], status="sent")
        .order_by("-sent_at")
        .values_list("sent_at", flat=True)
        .first()
    ) or invoice.date_sent
    if not last:
        return None
    return max((timezone.now() - last).days, 0)


def send_reminder(
    invoice,
    *,
    to=None,
    cc=None,
    message=None,
    attach_pdf=False,
    sent_by=None,
    request=None,
):
    """Email a payment reminder for an already-sent invoice. Returns True.

    The reminder notes how many days ago the invoice went out, the firm's own
    payment terms when it has set any (Settings, Firm), and that
    accommodations are available on request. attach_pdf optionally attaches a
    courtesy copy of the invoice PDF (off by default — it's downloadable at
    the pay link). Logs a 'reminder'-kind transmission; the invoice's status,
    date_sent, and ×N send tally are untouched.
    """
    matter = invoice.matter
    client = matter.client if matter else None
    to_list = _parse_recipients(to)
    if not to_list and client and client.email:
        to_list = [client.email.strip()]
    cc_list = _parse_recipients(cc)
    to_joined = ", ".join(to_list)
    cc_joined = ", ".join(cc_list)

    if not to_list:
        _log(
            invoice,
            to_email="",
            cc_email=cc_joined,
            sent_by=sent_by,
            status="failed",
            error="No client email address on file.",
            kind="reminder",
        )
        raise InvoiceSendError("This matter's client has no email address on file.")

    invalid = _invalid_addresses(to_list + cc_list)
    if invalid:
        error = f"Invalid email address(es): {', '.join(invalid)}"
        _log(
            invoice,
            to_email=to_joined,
            cc_email=cc_joined,
            sent_by=sent_by,
            status="failed",
            error=error,
            kind="reminder",
        )
        raise InvoiceSendError(error)

    try:
        if attach_pdf and not invoice.pdf_file:
            store_invoice_pdf(invoice, request)

        company = Firm.objects.first()
        bcc_list = _parse_recipients(company.invoice_bcc) if company else []
        billing_email = ""
        if company:
            billing_email = company.billing_email or company.email
        context = {
            "invoice": invoice,
            "matter_name": matter.name if matter else "",
            "matter_number": matter.id if matter else "",
            "client_name": client.name if client else "",
            "amount_due": invoice.amount_remaining,
            "cover_message": message or "",
            "days_since": days_since_sent(invoice),
            "payment_terms": company.payment_terms if company else "",
            "firm_name": company.name if company else "",
            "billing_email": billing_email,
            **_invoice_links(invoice, request),
            "attach_pdf": attach_pdf,
            "logo_cid": FIRM_LOGO_CID if company and company.email_logo else "",
            "firm_address": firm_postal_address(company),
        }
        firm = company.name if company else ""
        subject = f"{firm} - " if firm else ""
        subject += f"Payment Reminder - Invoice {invoice.id}"

        email = EmailMultiAlternatives(
            subject=subject,
            body=render_to_string("emails/invoice_reminder_email.txt", context),
            from_email=billing_from_email(company),
            to=to_list,
            cc=cc_list,
            bcc=bcc_list or None,
            reply_to=[billing_reply_to(company)] if billing_email else None,
        )
        email.attach_alternative(
            render_inlined("emails/invoice_reminder_email.html", context), "text/html"
        )
        if attach_pdf:
            with invoice.pdf_file.open("rb") as f:
                email.attach(f"invoice_{invoice.id}.pdf", f.read(), "application/pdf")
        # After the PDF: with a document attached the root must stay mixed
        # (attach_firm_logo only switches to related when attachments is empty).
        if context["logo_cid"]:
            attach_firm_logo(email, company)
        email.send()
    except Exception as exc:
        _log(
            invoice,
            to_email=to_joined,
            cc_email=cc_joined,
            sent_by=sent_by,
            status="failed",
            error=str(exc),
            kind="reminder",
        )
        raise InvoiceSendError(f"Could not send the reminder: {exc}") from exc

    _log(
        invoice,
        to_email=to_joined,
        cc_email=cc_joined,
        sent_by=sent_by,
        status="sent",
        kind="reminder",
    )
    return True
