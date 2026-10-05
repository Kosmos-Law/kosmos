from django import forms
from django.utils import timezone

from apps.invoicing.credits.models import Credit
from config.settings import CustomFormRendererCompact


class CreditsForm(forms.ModelForm):
    class Meta:
        model = Credit
        fields = [
            "date",
            "matter",
            "amount",
            "detail",
        ]
        widgets = {
            "matter": forms.Select(attrs={"class": ""}),
            "date": forms.DateInput(attrs={"type": "date", "class": ""}),
            "amount": forms.TextInput(attrs={"class": ""}),
            "detail": forms.TextInput(attrs={"required": False, "class": "span3"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.renderer = CustomFormRendererCompact()

        self.fields["date"].initial = timezone.localdate()

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Enter an amount greater than zero.")
        return amount

    def clean(self):
        """A credit already applied to invoices cannot shrink below what is
        applied, or move to another matter, as a payment cannot."""
        cleaned = super().clean()
        amount = cleaned.get("amount")
        matter = cleaned.get("matter")
        if not self.instance.pk or amount is None or matter is None:
            return cleaned
        applied = self.instance.amount - self.instance.amount_unapplied
        if not applied:
            return cleaned
        if amount < applied:
            self.add_error(
                "amount",
                f"${applied:,.2f} of this credit is applied to invoices. "
                "Remove an application first to make it smaller.",
            )
        if matter.pk != self.instance.matter_id:
            self.add_error(
                "matter",
                "This credit is applied to invoices on its matter. "
                "Remove the applications first to move it.",
            )
        return cleaned
