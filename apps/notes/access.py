"""Who may reach a note or a note folder.

A note or folder with no matter is in the firm's library: every signed-in
user may see it. One on a matter is for the people who may see that matter.
The /notes/ routes sit outside the central /case/ matter check, so every
view that takes a note, folder or matter id goes through here.

A refusal is a 404, the same answer as for an id that does not exist, so it
does not confirm that the record is there.
"""

from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.matters.models import Matter

from .models import Note, NoteFolder


def note_for_user(user, note_id, **filters):
    """The note, or 404 when it is missing or on a matter the user cannot see."""
    note = get_object_or_404(
        Note.objects.select_related("matter"), pk=note_id, **filters
    )
    if note.matter_id and not user.has_matter_access(note.matter):
        raise Http404
    return note


def folder_for_user(user, folder_id, **filters):
    """The folder, or 404 when it is missing or on a matter the user cannot see."""
    folder = get_object_or_404(
        NoteFolder.objects.select_related("matter", "parent"), pk=folder_id, **filters
    )
    if folder.matter_id and not user.has_matter_access(folder.matter):
        raise Http404
    return folder


def matter_for_user(user, matter_id):
    """The matter, or 404 when it is missing or not the user's to see."""
    matter = get_object_or_404(Matter, pk=matter_id)
    if not user.has_matter_access(matter):
        raise Http404
    return matter


def visible_notes_q(user, prefix=""):
    """A filter for the notes the user may see: the library's, and those on
    the user's matters. ``prefix`` reaches the note from another model
    ("note__" from a NoteView)."""
    if user.is_admin or user.perm_all_matters:
        return Q()
    return Q(**{f"{prefix}matter__isnull": True}) | Q(
        **{f"{prefix}matter__in": user.assigned_matters.all()}
    )
