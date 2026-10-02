"""What a user may do with time, expense and flat-fee entries.

The three entry types share these rules, so the views for each call the same
helpers: which entries a user can reach, which matters an entry form offers,
and when an entry is past editing.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404

from apps.accounts.access import filter_matters_for_user
from apps.matters.models import Matter

# Matters an entry form offers. A closed matter is offered only to the form
# opened from it, or to the entry already on it.
ENTRY_FORM_STATUSES = ("Pending", "Open", "Complete")

LOCKED_MESSAGE = "This entry is on a finalized invoice and can no longer be changed."


def entries_for_user(queryset, user):
    """Limit entries to the matters the user may see."""
    if user.is_admin or user.perm_all_matters:
        return queryset
    return queryset.filter(matter__in=user.assigned_matters.all())


def entry_for_user(model, pk, user):
    """The entry, or 404; refused when it is on a matter the user cannot see."""
    entry = get_object_or_404(model.objects.select_related("matter", "invoice"), pk=pk)
    if entry.matter_id and not user.has_matter_access(entry.matter):
        raise PermissionDenied
    return entry


def locked_response(entry):
    """A refusal when the entry is on an invoice that has left Draft, else None.

    The lists stop linking to such an entry; this stops the request itself.
    """
    if entry.locked:
        return HttpResponseForbidden(LOCKED_MESSAGE)
    return None


def matters_for_entry_form(user, billing_type=None, include_id=None):
    """The matter choices for an entry form, limited to what the user may see.

    ``include_id`` keeps one matter in the list whatever its status: the
    matter the form was opened from, or the one the entry is already on.
    """
    wanted = Q(status__in=ENTRY_FORM_STATUSES)
    if include_id:
        wanted |= Q(pk=include_id)
    matters = Matter.objects.filter(wanted)
    if billing_type:
        matters = matters.filter(billing_type=billing_type)
    return filter_matters_for_user(matters, user).order_by("name")
