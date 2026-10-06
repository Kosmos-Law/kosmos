from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from apps.matters.models import Matter


def matter_access_required(view_func):
    """Decorator for views with a matter id param. Checks user has access."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        matter_id = kwargs.get("id") or kwargs.get("matter_id")
        if matter_id:
            matter = get_object_or_404(Matter, pk=matter_id)
            if not request.user.has_matter_access(matter):
                raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper


def filter_matters_for_user(queryset, user):
    """If user lacks perm_all_matters, filter to assigned_matters."""
    if user.is_admin or user.perm_all_matters:
        return queryset
    return queryset.filter(members=user)


# Case-workspace routes name the thing they act on by its own id (a document,
# a fact, a conversation), not by matter. Each entry maps such a URL keyword
# to the model that owns it and the lookup that reaches its matter id, so a
# route's matter can be found without the view's help. A route that gains a
# new kind of id needs a line here to be covered.
_CASE = "apps.case.models"
_AI = "apps.case.ai.models"
MATTER_LOOKUPS = {
    "document_id": (f"{_CASE}.Document", ("matter_id",)),
    "highlight_id": (
        f"{_CASE}.Highlight",
        ("document__matter_id", "caselaw__matter_id"),
    ),
    "caselaw_id": (f"{_CASE}.CaseLaw", ("matter_id",)),
    "fact_id": (f"{_CASE}.Fact", ("matter_id",)),
    "witness_id": (f"{_CASE}.Witness", ("matter_id",)),
    "label_id": (f"{_CASE}.Label", ("matter_id",)),
    "note_id": ("apps.notes.models.Note", ("matter_id",)),
    "conv_id": (f"{_AI}.Conversation", ("matter_id",)),
    "message_id": (f"{_AI}.Message", ("conversation__matter_id",)),
    "email_id": ("apps.mail.models.Email", ("matter_id",)),
}

# The label and witness pickers take the object as a (type, id) pair.
OBJECT_TYPE_KEYS = {
    "document": "document_id",
    "highlight": "highlight_id",
    "fact": "fact_id",
    "note": "note_id",
    "caselaw": "caselaw_id",
    "witness": "witness_id",
}


def matter_ids_for_route(view_kwargs):
    """Ids of the matters a case-workspace route touches, from its URL
    keywords. An id that matches no row contributes nothing (the view will
    answer 404), as does a row with no matter (a library note, an intake
    chat)."""
    from django.utils.module_loading import import_string

    lookups = {}
    for key, value in view_kwargs.items():
        if key in MATTER_LOOKUPS:
            lookups[key] = value
    if "object_type" in view_kwargs and "object_id" in view_kwargs:
        key = OBJECT_TYPE_KEYS.get(view_kwargs["object_type"])
        if key:
            lookups[key] = view_kwargs["object_id"]

    matter_ids = set()
    if "matter_id" in view_kwargs:
        matter_ids.add(view_kwargs["matter_id"])
    for key, pk in lookups.items():
        model_path, fields = MATTER_LOOKUPS[key]
        row = import_string(model_path).objects.filter(pk=pk).values_list(*fields)
        for values in row[:1]:
            matter_ids.update(v for v in values if v is not None)
    return matter_ids


def user_may_use_route(user, view_kwargs):
    """False when the route touches a matter this user is not assigned to.
    Users who can see every matter are never looked up."""
    if user.is_admin or user.perm_all_matters:
        return True
    matter_ids = matter_ids_for_route(view_kwargs)
    if not matter_ids:
        return True
    allowed = Matter.objects.filter(pk__in=matter_ids, members=user).count()
    return allowed == len(matter_ids)
