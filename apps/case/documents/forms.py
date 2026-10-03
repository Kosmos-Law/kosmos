from django import forms
from django.db.models import Q

from apps.case.models import Document
from apps.matters.models import Matter
from apps.matters.proceedings.models import Proceeding
from config.settings import CustomFormRendererCompact

from .access import open_matters_for_user


class ProceedingChoiceField(forms.ModelChoiceField):
    """Custom field to display proceedings with nickname if available."""

    def label_from_instance(self, obj):
        return f"{obj.display_name} - {obj.case_number}"


class FilesForm(forms.ModelForm):
    matter = forms.ModelChoiceField(
        queryset=Matter.objects.none(),
        required=True,
        empty_label=None,
    )
    proceeding = ProceedingChoiceField(
        queryset=Proceeding.objects.none(),
        required=False,
        empty_label="Select Proceeding",
    )

    class Meta:
        model = Document
        fields = [
            "matter",
            "category",
            "proceeding",
            "date",
            "name",
            "description",
            "ai_context",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "name": forms.TextInput(attrs={"class": "span2"}),
            "description": forms.Textarea(attrs={"class": "span2", "rows": 2}),
            "ai_context": forms.Select(),
        }

    def __init__(
        self,
        *args,
        matter=None,
        user=None,
        initial_category=None,
        initial_proceeding=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.renderer = CustomFormRendererCompact()
        self.matter = matter

        # Matter choices: the Open matters the user may see, plus the matter
        # the document is on (or is being added to) whatever its status. The
        # field has no blank choice, so a document whose own matter were
        # missing from the list would be moved to the first one on Submit.
        current_id = self.instance.matter_id if self.instance.pk else None
        if current_id is None and matter:
            current_id = matter.pk
        if user:
            queryset = open_matters_for_user(user, include_id=current_id)
        else:
            queryset = Matter.objects.filter(
                Q(status="Open") | Q(pk=current_id)
            ).order_by("name")
        self.fields["matter"].queryset = queryset

        # A document that came from Google Drive follows its folder there:
        # the sync puts it back on the folder's matter, so its matter is
        # shown and cannot be changed here. (A disabled field also ignores
        # whatever is posted for it.)
        if self.instance.pk and self.instance.is_drive_synced:
            self.fields["matter"].disabled = True

        # If matter provided (new document), set it as initial
        if matter:
            self.fields["matter"].initial = matter
            self.fields["proceeding"].queryset = matter.proceeding_set.all().order_by(
                "forum", "case_number"
            )
            # Set initial proceeding for new documents: filter value > primary > none
            if not self.instance.pk:
                if initial_proceeding:
                    self.fields["proceeding"].initial = initial_proceeding
                else:
                    primary = matter.proceeding_set.filter(primary=True).first()
                    if primary:
                        self.fields["proceeding"].initial = primary
        # If editing and has a matter, show proceedings for that matter
        elif self.instance.pk and self.instance.matter:
            self.fields[
                "proceeding"
            ].queryset = self.instance.matter.proceeding_set.all().order_by(
                "forum", "case_number"
            )
        else:
            self.fields["proceeding"].queryset = Proceeding.objects.none()

        # Set initial category from filter (for new documents only)
        if initial_category and not self.instance.pk:
            self.fields["category"].initial = initial_category

    def clean(self):
        cleaned_data = super().clean()
        matter = cleaned_data.get("matter")
        proceeding = cleaned_data.get("proceeding")
        category = cleaned_data.get("category")

        # Clear proceeding if matter changed and proceeding doesn't belong to new matter
        if proceeding and matter and proceeding.matter_id != matter.id:
            cleaned_data["proceeding"] = None

        # Clear proceeding if category is not Record or Discovery
        if proceeding and category not in ("Record", "Discovery"):
            cleaned_data["proceeding"] = None

        return cleaned_data


class BulkFilesForm(forms.ModelForm):
    proceeding = ProceedingChoiceField(
        queryset=Proceeding.objects.none(),
        required=False,
        empty_label="Select Proceeding",
    )

    class Meta:
        model = Document
        fields = ["proceeding"]

    def __init__(self, *args, matter=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.renderer = CustomFormRendererCompact()
        self.matter = matter

        if matter:
            self.fields["proceeding"].queryset = matter.proceeding_set.all().order_by(
                "forum", "case_number"
            )
        else:
            self.fields["proceeding"].queryset = Proceeding.objects.none()
