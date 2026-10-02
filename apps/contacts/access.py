"""What a user may see and do with a contact's place on matters.

Contacts themselves are the firm's: every signed-in user sees them. What a
contact page shows about matters and money is not. A user limited to assigned
matters sees and changes only those matters' parties, and a client's trust
balances are for users with the Financial permission. The contact page and the
matter's Contacts tab both go through these helpers, so the two agree.
"""

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from apps.accounts.access import filter_matters_for_user
from apps.matters.models import Matter, Relationship, Role

# The sidebar's Clients lists. A contact's derived status can also be
# "Nonclient", which has no list of its own.
CLIENT_LISTS = ("Pending", "Current", "Former")

# The client mirror row (Matter.client in the Client role) is managed via the
# matter, not the parties list.
CLIENT_ROW_GUARD_MSG = "The client is managed on the matter, not the parties list."


def can_see_trust(user):
    """Trust balances are financial: admins and the Financial permission."""
    return user.is_admin or user.perm_financial


def matters_for_user(user):
    """The matters this user may see."""
    return filter_matters_for_user(Matter.objects.all(), user)


def matter_for_user(pk, user):
    """The matter, or 404; refused when it is not the user's to see."""
    matter = get_object_or_404(Matter, pk=pk)
    if not user.has_matter_access(matter):
        raise PermissionDenied
    return matter


def relationships_for_user(queryset, user):
    """Limit party rows to the matters the user may see."""
    if user.is_admin or user.perm_all_matters:
        return queryset
    return queryset.filter(matter__in=user.assigned_matters.all())


def relationship_for_user(pk, user):
    """The party row, or 404; refused when its matter is not the user's."""
    relationship = get_object_or_404(
        Relationship.objects.select_related("matter", "contact", "role", "group"),
        pk=pk,
    )
    if not user.has_matter_access(relationship.matter):
        raise PermissionDenied
    return relationship


def is_client_mirror(relationship):
    """True only for the row that mirrors Matter.client (that contact in the
    Client role). Co-clients — the Client role on a different contact — are not
    mirrors and stay fully editable."""
    return (
        relationship.matter.client_id == relationship.contact_id
        and relationship.role.is_system
    )


def assignable_roles():
    """The roles an assign dialog offers. The system Client role marks the
    matter's own client, which is set on the matter; neither it nor
    "Client (Invoicing)" is handed out from a dialog. One list, so the
    matter's Contacts tab and the contact page cannot drift apart."""
    return (
        Role.objects.filter(is_active=True)
        .exclude(is_system=True)
        .exclude(name="Client (Invoicing)")
        .order_by("name")
    )


def already_assigned(matter, contact, group, role):
    """Whether this exact party row exists. A contact may hold several roles
    on one matter; the same role in the same group twice is only a duplicate."""
    return Relationship.objects.filter(
        matter=matter, contact=contact, group=group, role=role
    ).exists()


def posted_ids(request, *names):
    """The named ids from the POST body as ints, or None when any is missing
    or not a number. An empty dropdown or an unpicked contact sends nothing
    (or an empty string), which a lookup by primary key turns into a server
    error."""
    ids = {}
    for name in names:
        value = (request.POST.get(name) or "").strip()
        if not value.isdigit():
            return None
        ids[name] = int(value)
    return ids
