from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.urls import reverse

from apps.management.templatetags.phone_numbers import phone_number
from apps.settings.models import Firm
from config.helpers import normalize_phone

MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2MB
# The logo is an ImageField, which is validated with Pillow, and Pillow does
# not read SVG: offering it only produced an upload that was always refused.
ALLOWED_LOGO_TYPES = ["image/png", "image/jpeg"]

# The logo slots on the firm page, in display order: the Firm field, its
# label, and the help text under its file chooser. One upload form each
# (firm_logo_form); the dark and email slots fall back to the logo.
LOGO_SLOTS = {
    "logo": (
        "Logo",
        "Shown on light themes, PDFs and the public intake pages. "
        "PNG or JPG, max 2 MB.",
    ),
    "logo_dark": (
        "Dark-theme logo",
        "Stands in for the logo on dark themes: light ink on a transparent "
        "ground. Without one, dark themes show the logo.",
    ),
    "logo_email": (
        "Email logo",
        "Embedded in invoice and intake emails, where the reader's theme is "
        "unknown: art on a solid white ground reads in either. Without one, "
        "emails carry the logo.",
    ),
}


class FirmForm(forms.ModelForm):
    """Firm-settings form: contact details, invoice BCC, and research
    jurisdiction — saved together by the "Save Firm Details" button.

    The logo is intentionally NOT part of this form: it uploads/removes on its
    own (see firm_logo_form + the firm-upload-logo/firm-remove-logo endpoints),
    so changing a logo never depends on saving the rest of the details."""

    class Meta:
        model = Firm
        fields = [
            "name",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "zip_code",
            "phone",
            "email",
            "billing_email",
            "invoice_bcc",
            "intake_email",
            "jurisdiction",
            "payment_terms",
            "invoice_trust_note",
        ]
        widgets = {
            "invoice_bcc": forms.Textarea(attrs={"rows": 2}),
            "invoice_trust_note": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "billing_email": "Billing Email",
            "invoice_bcc": "Invoice BCC",
            "intake_email": "Intake Email",
            "payment_terms": "Payment Terms",
            "invoice_trust_note": "Invoice Trust Note",
        }
        help_texts = {
            "payment_terms": "One sentence added to payment reminders, for example the terms in your fee agreement. Leave blank to say nothing.",
            "invoice_trust_note": "Printed under Funds in Trust on an invoice when the client holds money in trust. Leave blank to print the balance alone.",
            "jurisdiction": "Used for a matter that has no jurisdiction of its own: on its Overview, and in AI chat and intake assessments.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        text_fields = [
            "name",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "zip_code",
            "phone",
            "email",
            "billing_email",
            "invoice_bcc",
            "intake_email",
            "jurisdiction",
        ]
        # Keep browsers from offering to "save this address". Firefox/Chrome
        # capture addresses when they *classify* a group of fields as one — on
        # submit AND on navigation — and they ignore autocomplete="off" for that.
        # Tagging every field with a recognized *non-address* token
        # ("one-time-code") makes them classify each field by that token instead
        # of by its name, so no address profile is ever assembled to capture.
        # (Paired with the template posting via a button, not a <form> submit.)
        for field_name in text_fields:
            self.fields[field_name].widget.attrs["autocomplete"] = "one-time-code"

        # Show the stored digits formatted as (XXX) XXX-XXXX in the input;
        # clean_phone normalizes back to raw digits on save.
        if not self.is_bound and self.instance and self.instance.phone:
            self.initial["phone"] = phone_number(self.instance.phone)

    def clean_phone(self):
        """Normalize to raw digits (+ optional extension), matching contacts."""
        value = self.cleaned_data.get("phone", "")
        if value:
            normalized, is_valid = normalize_phone(value)
            if not is_valid:
                raise ValidationError("Enter a valid 10-digit US phone number.")
            return normalized
        return value

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


class FirmLogoForm(forms.ModelForm):
    """Base of the one-field upload forms built by firm_logo_form: validates
    whichever slot the form carries."""

    class Meta:
        model = Firm
        fields = ["logo"]

    def clean(self):
        cleaned = super().clean()
        (slot,) = self._meta.fields
        logo = cleaned.get(slot)
        if not logo or not hasattr(logo, "content_type"):
            return cleaned
        if logo.content_type not in ALLOWED_LOGO_TYPES:
            self.add_error(slot, "Only PNG and JPG files are allowed.")
        elif logo.size > MAX_LOGO_SIZE:
            self.add_error(slot, "Logo must be under 2 MB.")
        return cleaned


def firm_logo_form(slot, *args, **kwargs):
    """The upload form for one logo slot — auto-submits on file selection,
    independent of the main firm-details form."""
    widget = forms.FileInput(
        attrs={
            "accept": ".png,.jpg,.jpeg",
            # Auto-upload the moment a file is chosen; CSRF rides on the
            # global hx-headers set on <body>.
            "hx-post": reverse("settings:firm-upload-logo", args=[slot]),
            "hx-trigger": "change",
            "hx-target": f"#firm-logo-{slot}",
            "hx-encoding": "multipart/form-data",
        }
    )
    form_class = forms.modelform_factory(
        Firm,
        form=FirmLogoForm,
        fields=[slot],
        widgets={slot: widget},
        help_texts={slot: LOGO_SLOTS[slot][1]},
    )
    return form_class(*args, **kwargs)
