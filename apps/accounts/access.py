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
# a fact, a conversation), not by matter. Each lookup maps such a URL keyword
# to the model that owns it and the fields that reach its matter id, so a
# route's matter can be found without the view's help. The apps that own the
# rows register their lookups at start-up (the case app in
# apps/case/registrations.py, the AI and mail apps in their AppConfigs); a
# route that gains a new kind of id needs a registration to be covered.
MATTER_LOOKUPS = {}

# The label and witness pickers take the object as a (type, id) pair.
OBJECT_TYPE_KEYS = {}


def register_matter_lookup(key, model, fields, object_type=None):
    """Cover routes whose URL keyword ``key`` is a ``model`` id; ``fields``
    are the lookups from a row to its matter id. ``object_type`` is the
    (type, id) pair's name for the same rows, when the pickers take one."""
    MATTER_LOOKUPS[key] = (model, tuple(fields))
    if object_type:
        OBJECT_TYPE_KEYS[object_type] = key


def matter_ids_for_route(view_kwargs):
    """Ids of the matters a case-workspace route touches, from its URL
    keywords. An id that matches no row contributes nothing (the view will
    answer 404), as does a row with no matter (a library note, an intake
    chat)."""
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
        model, fields = MATTER_LOOKUPS[key]
        row = model.objects.filter(pk=pk).values_list(*fields)
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
