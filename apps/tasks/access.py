"""What a user may do with tasks.

A task on a matter follows that matter: a user limited to assigned matters
reaches it only when the matter is theirs. A task on no matter ("Admin") is
the firm's, so every signed-in user may reach it. The firm-wide tasks views,
the notes on a task and the checklist attached to one all call the same
helpers: which tasks a user can reach, and which matters a task form offers.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.accounts.access import filter_matters_for_user
from apps.matters.models import Matter
from apps.tasks.models import Task, TaskNote

# Matters a task form or the tasks filter offers. A matter in another status
# is offered only to the form opened from it, or to the task already on it.
TASK_MATTER_STATUSES = ("Pending", "Open")


def sees_all_matters(user):
    return user.is_admin or user.perm_all_matters


def tasks_for_user(queryset, user):
    """Limit tasks to those on no matter and those on the user's matters."""
    if sees_all_matters(user):
        return queryset
    return queryset.filter(
        Q(matter__isnull=True) | Q(matter__in=user.assigned_matters.all())
    )


def task_for_user(pk, user, **lookup):
    """The task, or 404; refused when it is on a matter the user cannot see."""
    task = get_object_or_404(Task.objects.select_related("matter"), pk=pk, **lookup)
    if task.matter_id and not user.has_matter_access(task.matter):
        raise PermissionDenied
    return task


def task_note_for_user(pk, user):
    """The note, or 404; refused when its task is not the user's to see."""
    note = get_object_or_404(TaskNote.objects.select_related("task__matter"), pk=pk)
    task = note.task
    if task.matter_id and not user.has_matter_access(task.matter):
        raise PermissionDenied
    return note


def matter_for_user(pk, user):
    """The matter, or 404; refused when the user cannot see it."""
    matter = get_object_or_404(Matter, pk=pk)
    if not user.has_matter_access(matter):
        raise PermissionDenied
    return matter


def matters_for_task_form(user, include_id=None):
    """The matter choices for a task form, limited to what the user may see.

    ``include_id`` keeps one matter in the list whatever its status: the
    matter the form was opened from, or the one the task is already on.
    """
    wanted = Q(status__in=TASK_MATTER_STATUSES)
    if include_id:
        wanted |= Q(pk=include_id)
    return filter_matters_for_user(Matter.objects.filter(wanted), user).order_by("name")
