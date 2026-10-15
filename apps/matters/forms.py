from django import forms
from django.db.models import Q

from apps.calendar.widgets import CheckSelect
from apps.contacts.models import Contact
from config.helpers import YESNO_CHOICES
from config.settings import CustomFormRendererCompact

from .models import Group, Matter, PracticeArea


class ContactComboboxWidget(forms.Widget):
    """Typeahead combobox for choosing a contact. Renders a search input plus a
    hidden value input that carries the field's value on submit. Reuses
    static/js/combobox.js and the contact-search results partial
    (templates/matters/contacts/results.html, served by matters:client-search)."""

    template_name = "matters/widgets/contact_combobox.html"

    def id_for_label(self, id_):
        # The label points at the visible search input (the id combobox.js binds
        # to), not the hidden value input.
        return "assign-search-input"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        selected_name = ""
        if value not in (None, ""):
            contact = Contact.objects.filter(pk=value).first()
            selected_name = contact.name if contact else ""
        context["widget"]["selected_name"] = selected_name
        return context


class MatterForm(forms.ModelForm):
    class Meta:
        model = Matter

        fields = (
            "client",
            "billing_contacts",
            "status",
            "date_start",
            "name",
            "practice_area",
            "description",
            "work_status",
            "jurisdiction",
            "billable",
            "billing_type",
            "deferred_fees",
            "flat_fee_amount",
        )

        STATUSES = Matter.STATUS_CHOICES

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "onfocus": "moveFocusToEnd(this)",
                    "class": "span2",
                }
            ),
            "description": forms.TextInput(
                attrs={
                    "class": "span3",
                }
            ),
            "work_status": forms.TextInput(
                attrs={
                    "class": "span2",
                }
            ),
            "status": forms.Select(
                choices=STATUSES,
            ),
            "client": ContactComboboxWidget(),
            # Ticked in a dropdown of check rows; the button reads the one
            # name, or how many are ticked
            "billing_contacts": CheckSelect(empty_label="None", many_label="copied"),
            "date_start": forms.DateInput(attrs={"type": "date"}),
            "jurisdiction": forms.TextInput(),
            "billable": forms.Select(
                choices=((True, "Yes"), (False, "No (Administrative)")),
            ),
            "billing_type": forms.Select(
                attrs={"onchange": "toggleFlatFeeAmount()"},
            ),
            "flat_fee_amount": forms.NumberInput(
                attrs={"step": "0.01"},
            ),
            "deferred_fees": forms.Select(choices=YESNO_CHOICES),
        }

        labels = {
            "name": "Matter Name",
            "date_start": "Open Date",
            "clio_matter_id": "Clio Matter",
            "client_reference_id": "Client Reference",
            "practice_area": "Practice Area",
            "billing_contacts": "Additional Billing Contacts",
            "billing_type": "Billing Type",
            "flat_fee_amount": "Flat Fee Amount",
            "deferred_fees": "Deferred Fee Arrangement",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.renderer = CustomFormRendererCompact()

        # client is nullable on the model but not blank, so the form would force
        # it; relax it here so administrative matters with no client can save.
        # (name/description/work_status get their optionality from the model.)
        self.fields["client"].required = False

        # Any contact can be a matter's client (the typeahead searches all
        # contacts), so validate the submitted pk against the full set.
        self.fields["client"].queryset = Contact.objects.all()

        # The billing contacts (copied on the matter's invoices and payment
        # requests) are ticked from the matter's own Client group: the
        # people on the client's side with an email, other than the client,
        # who is already the To. Anyone already ticked stays on the list even
        # if they have since lost their email or moved group, so an unrelated
        # edit never unticks them. A new matter has no contacts yet, and a
        # matter with no one to choose has nothing to show, so the field
        # appears only once there is someone to pick.
        matter = self.instance if self.instance.pk else None
        candidates = Contact.objects.none()
        if matter:
            client_group = Group.objects.client_group()
            candidates = (
                Contact.objects.filter(
                    Q(relationship__matter=matter, relationship__group=client_group)
                    & ~Q(email__isnull=True)
                    & ~Q(email="")
                    | Q(billing_matters=matter)
                )
                .exclude(pk=matter.client_id)
                .distinct()
                .order_by("name")
            )
        if candidates.exists():
            self.fields["billing_contacts"].queryset = candidates
        else:
            del self.fields["billing_contacts"]

        # Validate server-side (as the add view already does) rather than via
        # the HTML5 `required` attribute. Otherwise the browser silently refuses
        # to submit the edit modal when a required field is empty or not
        # focusable, with no error shown to the user.
        self.use_required_attribute = False

        # Filter practice areas to only show active ones
        self.fields["practice_area"].queryset = PracticeArea.objects.filter(
            is_active=True
        )
