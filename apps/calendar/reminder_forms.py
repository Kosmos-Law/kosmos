"""The form that adds a notification to an event."""

from django import forms

from apps.calendar.models import EventReminder
from utils.models import CHANNEL_CHOICES, ReminderMixin


class ReminderForm(forms.ModelForm):
    """One notification: an amount, a unit, for an all-day event the time
    of day, and the channel it goes by. A timed event counts back from
    its start; an all-day event counts back in days or weeks to a time
    of day. ``user`` sets the channel offered first (their default in
    Settings) and whether Push is offered at all (once ntfy is set up)."""

    use_required_attribute = False

    class Meta:
        model = EventReminder
        fields = ("amount", "unit", "time", "channel")
        widgets = {
            "amount": forms.NumberInput(attrs={"min": 0}),
            "time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, event, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.user = user
        self.fields["channel"].choices = [
            choice
            for choice in CHANNEL_CHOICES
            if choice[0] != "ntfy" or user.ntfy_topic
        ]
        # Left out, the channel is the user's default
        self.fields["channel"].required = False
        self.initial.setdefault("channel", user.notify_by)
        self.all_day = not event.start_time
        if self.all_day:
            self.fields["unit"].choices = [
                choice
                for choice in ReminderMixin.UNIT_CHOICES
                if choice[0] in ReminderMixin.ALL_DAY_UNITS
            ]
            self.initial.setdefault("amount", 1)
            self.initial.setdefault("unit", "days")
            self.initial.setdefault("time", ReminderMixin.DEFAULT_TIME)
        else:
            self.initial.setdefault("amount", 30)
            self.initial.setdefault("unit", "minutes")

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("channel"):
            cleaned_data["channel"] = self.user.notify_by
        if self.all_day:
            if cleaned_data.get("unit") not in ReminderMixin.ALL_DAY_UNITS:
                self.add_error("unit", "With no time set, count back in days or weeks.")
            if not cleaned_data.get("time"):
                cleaned_data["time"] = ReminderMixin.DEFAULT_TIME
        else:
            cleaned_data["time"] = None
        return cleaned_data
