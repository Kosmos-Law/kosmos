from django import forms

from apps.matters.rates.models import Rate
from config.settings import CustomFormRendererCompact


class RateForm(forms.ModelForm):
    class Meta:
        model = Rate

        fields = (
            "user",
            "matter_rate",
        )

    def __init__(self, *args, matter=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.renderer = CustomFormRendererCompact()
        self.matter = matter

    def clean_user(self):
        """One rate per user on a matter: a second would leave it unclear
        which one a new time entry takes."""
        user = self.cleaned_data.get("user")
        if user and self.matter:
            taken = Rate.objects.filter(matter=self.matter, user=user)
            if self.instance.pk:
                taken = taken.exclude(pk=self.instance.pk)
            if taken.exists():
                raise forms.ValidationError(
                    "This user already has a rate on this matter. Edit that rate instead."
                )
        return user
