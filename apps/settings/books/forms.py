from django import forms

from apps.settings.models import Firm


class BooksSettingsForm(forms.ModelForm):
    """Settings > Books: the return the firm files and the basis it keeps
    its books on."""

    class Meta:
        model = Firm
        fields = ["tax_form", "accounting_basis"]
        labels = {"tax_form": "Tax return", "accounting_basis": "Accounting basis"}
        help_texts = {
            "tax_form": (
                "Schedule C for a sole proprietor or a single-member LLC; "
                "Form 1120-S once the firm has elected S corporation status. "
                "Picks which tax-line mapping the Tax Summary reads."
            ),
            "accounting_basis": (
                "Cash counts income when a payment lands and expenses when "
                "they are paid; accrual counts invoices and bills when they "
                "are issued. Most small firms file on the cash basis."
            ),
        }
