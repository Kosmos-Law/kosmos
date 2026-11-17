from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.settings.models import Firm


class BillingForm(forms.ModelForm):
    """Settings > Billing: where replies to billing email go, who is copied
    on it, and the firm's own wording on invoices and reminders. The fields
    are on the Firm record, beside its details (Settings > Firm)."""

    class Meta:
        model = Firm
        fields = [
            "billing_email",
            "invoice_bcc",
            "payment_terms",
            "invoice_trust_note",
        ]
        widgets = {
            "invoice_bcc": forms.Textarea(attrs={"rows": 2}),
            "payment_terms": forms.Textarea(attrs={"rows": 3}),
            "invoice_trust_note": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "billing_email": "Billing Email",
            "invoice_bcc": "Invoice BCC",
            "payment_terms": "Payment Terms",
            "invoice_trust_note": "Invoice Trust Note",
        }
        help_texts = {
            "billing_email": "Where a client's reply to an invoice, payment request or reminder goes, and the contact address printed in them. Blank uses the firm's Email.",
            "invoice_bcc": "Addresses, separated by commas, that get a blind copy of every invoice, payment request and reminder email.",
            "payment_terms": "Printed at the foot of every invoice and in the invoice and reminder emails, for example the terms in your fee agreement. Leave blank to say nothing.",
            "invoice_trust_note": "Printed under Funds in Trust on an invoice when the client holds money in trust. Leave blank to print the balance alone.",
        }

    def clean_invoice_bcc(self):
        """Normalize + validate the comma/semicolon-separated BCC list."""
        raw = self.cleaned_data.get("invoice_bcc", "")
        addresses = [a.strip() for a in raw.replace(";", ",").split(",") if a.strip()]
        invalid = []
        for addr in addresses:
            try:
                validate_email(addr)
            except ValidationError:
                invalid.append(addr)
        if invalid:
            raise ValidationError(f"Invalid email address(es): {', '.join(invalid)}")
        return ", ".join(addresses)
