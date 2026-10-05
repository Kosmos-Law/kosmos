from django import forms
from django.utils import timezone

from apps.invoicing.payments.models import Payment
from apps.invoicing.payments.trust import TRUST_METHOD, trust_balance
from config.settings import CustomFormRendererCompact


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            "matter",
            "date",
            "payment_method",
            "amount",
            "detail",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "matter": forms.Select(attrs={"class": ""}),
            "payment_method": forms.Select(),
            "amount": forms.TextInput(attrs={"class": ""}),
            "detail": forms.TextInput(attrs={"required": False, "class": "span2"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.renderer = CustomFormRendererCompact()

        self.fields["date"].initial = timezone.localdate()
        self.fields["payment_method"].initial = "CARD"

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Enter an amount greater than zero.")
        return amount

    def clean(self):
        cleaned = super().clean()
        matter = cleaned.get("matter")
        amount = cleaned.get("amount")
        if matter is None or amount is None:
            return cleaned

        if self.instance.pk:
            self._check_against_applications(matter, amount)
        if cleaned.get("payment_method") == TRUST_METHOD:
            self._check_trust_funds(matter, amount)
        return cleaned

    def _check_against_applications(self, matter, amount):
        """A payment already applied to invoices cannot shrink below what is
        applied, or move to another matter: its applications would be left
        on invoices it no longer covers."""
        applied = self.instance.amount - self.instance.amount_unapplied
        if not applied:
            return
        if amount < applied:
            self.add_error(
                "amount",
                f"${applied:,.2f} of this payment is applied to invoices. "
                "Remove an application first to make it smaller.",
            )
        if matter.pk != self.instance.matter_id:
            self.add_error(
                "matter",
                "This payment is applied to invoices on its matter. "
                "Remove the applications first to move it.",
            )

    def _check_trust_funds(self, matter, amount):
        """A payment from trust cannot be more than the client holds."""
        if matter.client_id is None:
            self.add_error(
                "payment_method",
                "This matter has no client, so there is no trust balance to pay "
                "from. Set the client on the matter first.",
            )
            return
        balance = trust_balance(matter.client, excluding_payment=self.instance)
        if amount > balance:
            self.add_error(
                "amount",
                f"The client holds ${balance:,.2f} in trust, "
                "which is less than this payment.",
            )
