from django import forms

from apps.matters.proceedings.models import Proceeding
from config.helpers import YESNO_CHOICES
from config.settings import CustomFormRendererCompact


class ProceedingForm(forms.ModelForm):
    class Meta:
        model = Proceeding
        fields = (
            "date_filed",
            "nickname",
            "forum",
            "case_number",
            "status",
            "primary",
        )

        STATUSES = (
            ("Ongoing", "Ongoing"),
            ("Concluded", "Concluded"),
            ("Stayed", "Stayed"),
            ("Dismissed", "Dismissed"),
        )

        widgets = {
            "forum": forms.TextInput(attrs={"onfocus": "moveFocusToEnd(this)"}),
            "nickname": forms.TextInput(
                attrs={"placeholder": "Main, Appeal, Garnishment, etc. . . ."}
            ),
            "status": forms.Select(choices=STATUSES),
            "date_filed": forms.DateInput(attrs={"type": "date"}),
            "primary": forms.Select(choices=YESNO_CHOICES),
        }

        labels = {
            "date_filed": "Date Filed",
            "case_number": "Case Number",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.renderer = CustomFormRendererCompact()
