"""What a user may reach from the case file beyond the matter in the URL.

Every /case/ route is already refused centrally when its URL names a matter
the user is not on (apps/accounts/middleware.py). These helpers cover what
that check cannot see: a matter chosen in a form or sent in a POST body, and
lists that would otherwise reach across matters.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.accounts.access import filter_matters_for_user
from apps.matters.models import Matter


def matters_for_user(user):
    """Every matter the user may see, whatever its status."""
    return filter_matters_for_user(Matter.objects.all(), user)


def open_matters_for_user(user, include_id=None):
    """The matter choices for a document or label form: the Open matters the
    user may see.

    ``include_id`` keeps one matter in the list whatever its status: the
    matter the record is already on. Without it a record on a matter that is
    not Open has no selected choice, the browser picks the first one, and
    saving moves the record there.
    """
    allowed = filter_matters_for_user(Matter.objects.filter(status="Open"), user)
    wanted = Q(pk__in=allowed.values("pk"))
    if include_id:
        wanted |= Q(pk=include_id)
    return Matter.objects.filter(wanted).order_by("name")


def target_matter_for_user(matter_id, user):
    """The matter a POST names as a destination, or 404; refused when the
    user is not on it."""
    matter = get_object_or_404(Matter, pk=matter_id)
    if not user.has_matter_access(matter):
        raise PermissionDenied
    return matter


def documents_for_user(queryset, user):
    """Limit documents to the matters the user may see."""
    if user.is_admin or user.perm_all_matters:
        return queryset
    return queryset.filter(matter__in=user.assigned_matters.all())
