from django import forms

from apps.settings.models import Firm
from config.helpers import YESNO_CHOICES


def _switch(label, help_text):
    # The Select posts "True"/"False" strings, and bool("False") is True,
    # so coerce compares. Not required: a partial post reads as off.
    return forms.TypedChoiceField(
        coerce=lambda v: v in (True, "True"),
        choices=YESNO_CHOICES,
        required=False,
        label=label,
        help_text=help_text,
    )


class FeaturesForm(forms.ModelForm):
    """The firm-wide feature switches (Settings > Features)."""

    case_file_enabled = _switch(
        "Case File",
        "The case builder's workspace on each matter: documents, highlights, "
        "timeline, witnesses, emails, labels, search and the AI tab. Off "
        "removes Case from the sidebar and the link from the matter; the "
        "data stays and the Drive mirror pauses.",
    )
    library_enabled = _switch(
        "Library",
        "The notes: the editor, the firm library and the Notes tab of the "
        "case file. Off removes Library from the sidebar and notes from the "
        "firm-wide search; the notes stay.",
    )

    books_enabled = _switch(
        "Books",
        "The firm's ledger: the chart of accounts, journal entries and the "
        "financial statements behind invoicing and trust. On adds Books to "
        "the sidebar for users with the Books permission.",
    )

    class Meta:
        model = Firm
        fields = ["case_file_enabled", "library_enabled", "books_enabled"]

    def clean_books_enabled(self):
        return self.cleaned_data.get("books_enabled") or False

    def clean_case_file_enabled(self):
        return self.cleaned_data.get("case_file_enabled") or False

    def clean_library_enabled(self):
        return self.cleaned_data.get("library_enabled") or False
