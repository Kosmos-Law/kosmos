from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.accounts.models import ROLE_OPTIONS, CustomUser
from apps.matters.models import Matter
from apps.settings.users.filters import UserFilter
from apps.settings.users.forms import CreateUserForm, UserForm
from apps.settings.users.users import DEFAULT_USER_FILTER, get_user_list
from utils.toasts import toast_error


@login_required
def users_index(request):
    context = get_user_list(request)

    return render(request, "settings/users/index.html", context)


@login_required
def user_list(request):
    context = get_user_list(request)

    return render(request, "settings/users/user-table.html", context)


@login_required
def user_filter(request):
    if request.method == "POST":
        request.session["user_filter"] = request.POST

        return HttpResponse(status=204, headers={"HX-Trigger": "userListReload"})

    filter_data = request.session.get("user_filter", {})

    # If no filter data exists, apply default filter
    if not filter_data:
        filter_data = DEFAULT_USER_FILTER

    filter = UserFilter(
        filter_data, queryset=CustomUser.objects.all().order_by("username")
    )

    return render(request, "settings/users/filter.html", {"filter": filter})


def _is_last_admin(user):
    """True when ``user`` is the only active administrator. Settings are
    open to administrators alone, so a firm with none is locked out of them
    until someone uses the server's command line."""
    if not (user.is_admin and user.is_active):
        return False
    return (
        not CustomUser.objects.filter(role="ADMIN", is_active=True)
        .exclude(pk=user.pk)
        .exists()
    )


def _last_admin_refusal():
    response = HttpResponse(status=204)
    toast_error(
        response,
        "This is the only active administrator. "
        "Make another user an administrator first.",
    )
    return response


@login_required
def user_sort(request, order):
    # Sorting an unfiltered list keeps the list's default (active users
    # only): start from it, not from an empty filter.
    filter_data = dict(request.session.get("user_filter") or DEFAULT_USER_FILTER)

    current_order = filter_data.get("order_by", "")

    if current_order == order:
        new_order = f"-{order}" if not current_order.startswith("-") else order
    else:
        new_order = order

    filter_data["order_by"] = new_order
    request.session["user_filter"] = filter_data

    return HttpResponse(status=204, headers={"HX-Trigger": "userListReload"})


@login_required
@require_POST
def change_role(request, user_id, role):
    if role not in dict(ROLE_OPTIONS):
        return HttpResponseBadRequest()
    user = get_object_or_404(CustomUser, id=user_id)
    if role != "ADMIN" and _is_last_admin(user):
        return _last_admin_refusal()
    CustomUser.objects.filter(id=user_id).update(role=role)

    return HttpResponse(status=204, headers={"HX-Trigger": "userListReload"})


@login_required
@require_POST
def switch_status(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if user.is_active and _is_last_admin(user):
        return _last_admin_refusal()

    user.is_active = not user.is_active
    user.save()

    return HttpResponse(status=204, headers={"HX-Trigger": "userListReload"})


@login_required
def add_user(request):
    if request.method == "POST":
        form = CreateUserForm(request.POST)

        if form.is_valid():
            form.save()

            return HttpResponse(status=204, headers={"HX-Trigger": "userListReload"})
    else:
        form = CreateUserForm()

    context = {
        "form": form,
    }

    return render(request, "settings/users/new-user.html", context)


@login_required
def edit_user(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    was_last_admin = _is_last_admin(user)

    if request.method == "POST":
        form = UserForm(request.POST, instance=user)

        if form.is_valid():
            user = form.save(commit=False)
            if was_last_admin and not (user.is_admin and user.is_active):
                return _last_admin_refusal()
            user.save()

            return HttpResponse(status=204, headers={"HX-Trigger": "userListReload"})
    else:
        form = UserForm(instance=user)

    context = {
        "form": form,
    }

    return render(request, "settings/users/form.html", context)


@login_required
@require_POST
def toggle_permission(request, user_id, perm):
    if not request.user.is_admin:
        return HttpResponseForbidden()

    VALID_PERMS = [
        "perm_all_matters",
        "perm_financial",
        "perm_intakes",
        "perm_reports",
        "perm_research",
    ]
    if perm not in VALID_PERMS:
        return HttpResponseBadRequest()

    user = CustomUser.objects.get(id=user_id)
    setattr(user, perm, not getattr(user, perm))
    user.save(update_fields=[perm])

    return HttpResponse(
        status=204, headers={"HX-Trigger": "userListReload, permissionsChanged"}
    )


# Matters the assignment dialog lists: those still being worked. A new matter
# starts as Pending, and has to be assignable before it is opened.
ASSIGNABLE_STATUSES = ("Pending", "Open")


def _assignment_lists(target_user):
    """The dialog's two columns: the user's assigned matters, and the rest."""
    assigned = target_user.assigned_matters.filter(
        status__in=ASSIGNABLE_STATUSES
    ).order_by("name")
    unassigned = (
        Matter.objects.filter(status__in=ASSIGNABLE_STATUSES)
        .exclude(id__in=set(assigned.values_list("id", flat=True)))
        .order_by("name")
    )
    return assigned, unassigned


@login_required
def matter_assignments(request, user_id):
    """Render the matter assignment modal for a user."""
    if not request.user.is_admin:
        return HttpResponseForbidden()
    target_user = CustomUser.objects.get(id=user_id)
    assigned, unassigned = _assignment_lists(target_user)
    context = {
        "target_user": target_user,
        "assigned": assigned,
        "unassigned": unassigned,
    }
    return render(request, "settings/users/matter-assignments.html", context)


@login_required
@require_POST
def toggle_matter_assignment(request, user_id, matter_id):
    """Toggle a matter assignment for a user, then re-render modal body."""
    if not request.user.is_admin:
        return HttpResponseForbidden()
    target_user = CustomUser.objects.get(id=user_id)
    matter = Matter.objects.get(id=matter_id)
    if target_user.assigned_matters.filter(id=matter_id).exists():
        target_user.assigned_matters.remove(matter)
    else:
        target_user.assigned_matters.add(matter)
    # Re-render just the body partial
    assigned, unassigned = _assignment_lists(target_user)
    context = {
        "target_user": target_user,
        "assigned": assigned,
        "unassigned": unassigned,
    }
    return render(request, "settings/users/matter-assignments-body.html", context)
