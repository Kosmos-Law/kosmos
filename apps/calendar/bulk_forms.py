"""The dialogs of the event lists' bulk actions
(apps.calendar.selection_views): how far to move the selected events, and
who to assign them to."""

from django import forms

from apps.accounts.models import CustomUser
from config.settings import CustomFormRendererCompact

from .widgets import CheckSelect

# The furthest a bulk move goes either way: ten years
MAX_MOVE_DAYS = 3650


class BulkMoveForm(forms.Form):
    days = forms.IntegerField(
        label="Days",
        min_value=-MAX_MOVE_DAYS,
        max_value=MAX_MOVE_DAYS,
        widget=forms.NumberInput(attrs={"autofocus": True}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.renderer = CustomFormRendererCompact()

    def clean_days(self):
        days = self.cleaned_data["days"]
        if days == 0:
            raise forms.ValidationError("Enter a number of days other than 0.")
        return days


class BulkAssignForm(forms.Form):
    # Nobody ticked assigns the events to the firm, as on the event form
    assignees = forms.ModelMultipleChoiceField(
        label="Assigned to",
        queryset=CustomUser.objects.none(),
        required=False,
        widget=CheckSelect(empty_label="Firm"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.renderer = CustomFormRendererCompact()
        self.fields["assignees"].queryset = CustomUser.objects.filter(
            is_active=True
        ).order_by("first_name", "last_name")
        self.fields["assignees"].label_from_instance = lambda u: u.full_name
