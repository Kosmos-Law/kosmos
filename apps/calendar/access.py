"""What a user may do with calendar events.

An event on a matter belongs to that matter: a user limited to assigned
matters sees, opens and changes it only when the matter is one of theirs.
An event on no matter is the firm's, and every signed-in user may see it.
The lists, the calendar feed, the by-id views and the matter choices all
call these helpers so the rule lives in one place.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.accounts.access import filter_matters_for_user
from apps.calendar.models import Event
from apps.matters.models import Matter

# Matters the event form and the calendar's matter menu offer. A matter in
# any other status is offered only to the form opened from it, or to the
# event already on it.
EVENT_MATTER_STATUSES = Matter.ACTIVE_STATUSES


def events_for_user(queryset, user):
    """Limit events to those on matters the user may see, plus those on no
    matter."""
    if user.is_admin or user.perm_all_matters:
        return queryset
    return queryset.filter(
        Q(matter__isnull=True) | Q(matter__in=user.assigned_matters.all())
    )


def event_for_user(pk, user):
    """The event, or 404; refused when it is on a matter the user cannot see."""
    event = get_object_or_404(Event.objects.select_related("matter"), pk=pk)
    if event.matter_id and not user.has_matter_access(event.matter):
        raise PermissionDenied
    return event


def matters_for_events(user, include_id=None):
    """The matter choices for the event form and the calendar's matter menu,
    limited to what the user may see.

    ``include_id`` keeps one matter in the list whatever its status: the
    matter the form was opened from, or the one the event is already on.
    """
    wanted = Q(status__in=EVENT_MATTER_STATUSES)
    if include_id:
        wanted |= Q(pk=include_id)
    return filter_matters_for_user(Matter.objects.filter(wanted), user).order_by("name")
