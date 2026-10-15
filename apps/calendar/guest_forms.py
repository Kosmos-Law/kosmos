"""The form that invites a guest to an event."""

from django import forms

from apps.calendar.invitations import firm_member
from apps.calendar.models import EventGuest


class GuestForm(forms.ModelForm):
    """One guest: an address, and a name to address them by. Guests are
    people outside the firm; someone in it is refused with a pointer to
    the event's assignees, which is how the firm's own people are put on
    an event."""

    use_required_attribute = False

    class Meta:
        model = EventGuest
        fields = ("email", "name")
        widgets = {
            "email": forms.EmailInput(attrs={"placeholder": "Email"}),
            "name": forms.TextInput(attrs={"placeholder": "Name (optional)"}),
        }

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        member = firm_member(email)
        if member is not None:
            raise forms.ValidationError(
                f"{member} is in the firm. Add them as an assignee instead; "
                "guests are for people outside the firm."
            )
        if self.event.guests.filter(email__iexact=email).exists():
            raise forms.ValidationError("They are already invited.")
        return email
