"""Who may see intake data outside the Intakes pages.

Everything under /intakes/ is gated on the Intakes permission by
PermissionMiddleware. Views elsewhere that read an intake (the contact form
prefilled from one, the matter form's "Convert an intake" picker) are not
under that prefix, so they ask here.
"""

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from apps.contacts.models import Contact
from apps.intakes.models import Intake
from utils.toasts import toast_error


def can_see_intakes(user):
    return user.is_admin or user.perm_intakes


def require_intakes(user):
    """Refuse a user without the Intakes permission."""
    if not can_see_intakes(user):
        raise PermissionDenied


def contact_for_intake(intake):
    """The contact made from this intake, or None.

    One contact per intake is the rule, but nothing in the database enforces
    it, so where two exist the earliest stands in rather than raising."""
    return Contact.objects.filter(intake=intake).order_by("id").first()


def intake_for_new_contact(request):
    """The intake a contact form was opened from, as (intake, refusal).

    The form carries the intake's id in a hidden field. Linking is for users
    who may see intakes, and an intake takes one contact: a second submit
    (two people converting the same intake, or a double click) is refused
    with a message rather than making a twin. Both are None when the form
    was not opened from an intake."""
    intake_id = request.POST.get("intake_id")
    if not intake_id:
        return None, None
    require_intakes(request.user)
    intake = get_object_or_404(Intake, pk=intake_id)
    existing = contact_for_intake(intake)
    if existing:
        refusal = toast_error(
            HttpResponse(status=204),
            f"This intake is already in contacts as {existing.name}. "
            "No second contact was added.",
        )
        return None, refusal
    return intake, None
