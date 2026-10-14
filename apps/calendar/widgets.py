"""A set of choices behind a button, ticked in a dropdown of check rows
(templates/components/check-select.html): the form's counterpart of the
toolbar's check menus. The boxes are real checkboxes, so the form posts
them as a multiple choice; the button reads what is ticked."""

from django import forms


class CheckSelect(forms.CheckboxSelectMultiple):
    template_name = "components/check-select.html"

    def __init__(self, attrs=None, choices=(), *, empty_label="None"):
        super().__init__(attrs, choices)
        # What the button reads with nothing ticked
        self.empty_label = empty_label

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["empty_label"] = self.empty_label
        return context
