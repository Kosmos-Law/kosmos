"""A set of choices behind a button, ticked in a dropdown of check rows
(templates/components/check-select.html): the form's counterpart of the
toolbar's check menus. The boxes are real checkboxes, so the form posts
them as a multiple choice; the button reads what is ticked."""

from django import forms


class CheckSelect(forms.CheckboxSelectMultiple):
    template_name = "components/check-select.html"

    def __init__(
        self, attrs=None, choices=(), *, empty_label="None", many_label="assigned"
    ):
        super().__init__(attrs, choices)
        # What the button reads with nothing ticked, and the word after the
        # count when more than one is ("3 assigned", "2 copied")
        self.empty_label = empty_label
        self.many_label = many_label

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["empty_label"] = self.empty_label
        context["widget"]["many_label"] = self.many_label
        return context
