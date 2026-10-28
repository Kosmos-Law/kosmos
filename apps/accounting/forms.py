from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from apps.accounting.models import Account, JournalEntry, JournalLine
from apps.accounting.tax_lines import FORM_1120S, SCHEDULE_C, line_choices
from config.helpers import YESNO_CHOICES
from config.settings import CustomFormRendererCompact


class AccountForm(forms.ModelForm):
    schedule_c_line = forms.ChoiceField(
        choices=line_choices(SCHEDULE_C), required=False, label="Schedule C line"
    )
    form_1120s_line = forms.ChoiceField(
        choices=line_choices(FORM_1120S), required=False, label="1120-S line"
    )
    is_active = forms.TypedChoiceField(
        coerce=lambda v: v in (True, "True"),
        choices=YESNO_CHOICES,
        label="Active",
        initial=True,
    )

    class Meta:
        model = Account
        fields = [
            "code",
            "name",
            "subtype",
            "parent",
            "role",
            "schedule_c_line",
            "form_1120s_line",
            "description",
            "is_active",
        ]
        widgets = {
            "description": forms.TextInput(attrs={"class": "span2"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.renderer = CustomFormRendererCompact()
        self.fields["role"].required = False
        parents = Account.objects.filter(is_active=True)
        if self.instance.pk:
            parents = parents.exclude(pk=self.instance.pk)
        self.fields["parent"].queryset = parents
        self.fields["parent"].required = False
        self.fields["parent"].label = "Sub-account of"

    def clean(self):
        cleaned = super().clean()
        subtype = cleaned.get("subtype")
        if subtype:
            self.instance.type = Account.SUBTYPE_TYPE[subtype]
            if self.instance.type in Account.BALANCE_SHEET_TYPES:
                cleaned["schedule_c_line"] = ""
                cleaned["form_1120s_line"] = ""
        parent = cleaned.get("parent")
        if parent and subtype and parent.subtype != subtype:
            self.add_error("parent", "A sub-account has the same kind as its parent.")
        return cleaned


class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = ["date", "memo"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "memo": forms.TextInput(attrs={"class": "span2"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.renderer = CustomFormRendererCompact()
        if not self.instance.pk:
            self.fields["date"].initial = timezone.localdate()


class JournalLineForm(forms.ModelForm):
    class Meta:
        model = JournalLine
        fields = ["account", "debit", "credit", "memo"]
        widgets = {
            "debit": forms.TextInput(attrs={"inputmode": "decimal"}),
            "credit": forms.TextInput(attrs={"inputmode": "decimal"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(is_active=True)
        self.fields["account"].required = False
        self.fields["account"].empty_label = ""
        self.fields["debit"].required = False
        self.fields["credit"].required = False
        # A blank line starts blank, not at 0.00.
        if not self.instance.pk:
            self.initial["debit"] = ""
            self.initial["credit"] = ""

    def clean(self):
        cleaned = super().clean()
        debit = cleaned.get("debit") or 0
        credit = cleaned.get("credit") or 0
        if (debit or credit) and not cleaned.get("account"):
            self.add_error("account", "Pick an account.")
        if debit and credit:
            self.add_error("credit", "A line is a debit or a credit, not both.")
        if debit < 0 or credit < 0:
            self.add_error("debit", "Amounts are positive; swap the side.")
        cleaned["debit"] = debit
        cleaned["credit"] = credit
        return cleaned

    @property
    def is_blank(self):
        data = getattr(self, "cleaned_data", {})
        return not data.get("debit") and not data.get("credit")


JournalLineFormSet = inlineformset_factory(
    JournalEntry,
    JournalLine,
    form=JournalLineForm,
    extra=4,
    min_num=0,
    can_delete=False,
)


class PeriodForm(forms.Form):
    """The dates a statement covers. Blank falls back to the calendar year
    so far."""

    start = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def period(self):
        today = timezone.localdate()
        data = self.cleaned_data if self.is_valid() else {}
        start = data.get("start") or today.replace(month=1, day=1)
        end = data.get("end") or today
        if end < start:
            start, end = end, start
        return start, end
