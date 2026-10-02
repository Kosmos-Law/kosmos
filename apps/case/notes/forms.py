from django import forms

from apps.notes.access import matters_for_note_form
from apps.notes.models import Note
from config.settings import CustomFormRendererCompact


class NoteForm(forms.ModelForm):
    default_renderer = CustomFormRendererCompact

    class Meta:
        model = Note
        fields = ["matter", "category", "title"]
        widgets = {
            "matter": forms.Select(),
            "category": forms.Select(),
            "title": forms.TextInput(attrs={"class": "span2"}),
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop("matter", None)
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # Open matters the user may see, plus the note's own matter whatever
        # its status: without it the field opens blank on a matter that is
        # not Open and a plain rename cannot be saved
        self.fields["matter"].queryset = matters_for_note_form(
            user, include_id=self.instance.matter_id
        )
        # This form edits matter notes only; a note never leaves for the
        # library from here
        self.fields["matter"].required = True
        self.fields["matter"].empty_label = None
