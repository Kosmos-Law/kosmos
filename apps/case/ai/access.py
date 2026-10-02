"""Who may reach an AI conversation, and what its context may carry.

A conversation belongs to exactly one of a matter, an intake or one user's
agenda. Routes that name a matter conversation in the URL path are checked
for matter membership centrally (apps/accounts/middleware.py); that check
passes anything with no matter, and never sees an id that arrives in the
query string or the body. The helpers here cover both gaps.

The second half is about the reply rather than the route: the context and
the agent tools are built for the user who is asking, so money and case-law
research reach only the users who could open those screens.
"""

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from apps.accounts.access import filter_matters_for_user
from apps.matters.models import Matter

from .models import Conversation


def accessible_matters(user):
    """Every matter this user may open."""
    return filter_matters_for_user(Matter.objects.all(), user)


def user_may_use_conversation(user, conversation):
    """A matter chat needs the matter, an intake chat the Intakes
    permission, and an agenda chat is its owner's alone."""
    if conversation.matter_id:
        return user.has_matter_access(conversation.matter)
    if conversation.intake_id:
        return user.is_admin or user.perm_intakes
    if conversation.agenda_user_id:
        return conversation.agenda_user_id == user.id
    # Attached to nothing (should not happen): only whoever started it.
    return user.is_admin or conversation.user_id == user.id


def conversation_for_user(conv_id, user):
    """The conversation of any kind, or 404; refused when it is not this
    user's to see."""
    conversation = get_object_or_404(
        Conversation.objects.select_related("matter"), pk=conv_id
    )
    if not user_may_use_conversation(user, conversation):
        raise PermissionDenied
    return conversation


def matter_conversation_for_user(conv_id, matter, user):
    """A conversation named by an id from the query string or the body: it
    must be on the matter the URL names, and that matter must be the
    user's to see. Anything else is a 404, so the answer does not confirm
    that the conversation exists."""
    return get_object_or_404(
        Conversation,
        pk=conv_id,
        matter=matter,
        matter__in=accessible_matters(user),
    )


def has_financial_access(user):
    """Rates, fees, amounts and invoices: the Financial permission."""
    return bool(user) and (user.is_admin or user.perm_financial)


def has_research_access(user):
    """Case-law search: the Research permission."""
    return bool(user) and (user.is_admin or user.perm_research)
