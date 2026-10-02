"""What the Delete Folder dialog says will go.

"Delete Folder and Notes" on a folder with subfolders deletes the notes in
every subfolder, so the dialog counts those along with the folder's own.
"""

import pytest
from django.urls import reverse

from apps.notes.models import Note, NoteFolder

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree(user):
    """Library folder "Top" (no notes of its own) > "Mid" (2 notes) > "Deep"
    (1 note)."""
    top = NoteFolder.objects.create(name="Top")
    mid = NoteFolder.objects.create(name="Mid", parent=top)
    deep = NoteFolder.objects.create(name="Deep", parent=mid)
    for folder, title in ((mid, "One"), (mid, "Two"), (deep, "Three")):
        Note.objects.create(author=user, title=title, folder=folder)
    return top


class TestDialogCountsWhatWillGo:
    def test_notes_in_subfolders_are_counted(self, client, tree):
        html = client.get(
            reverse("notes:folder-delete-confirm", args=[tree.id])
        ).content.decode()
        assert "This folder contains 2 subfolders." in html
        assert "This folder and its subfolders contain 3 notes." in html
        # With notes anywhere in the tree the choice is spelled out as notes
        # deleted or kept; "Delete Folder and Subfolders" (which deletes the
        # subfolders' notes) is offered only when there are none to lose
        assert "Delete Folder and Notes" in html
        assert "Delete Folder, Keep Notes" in html
        assert "Delete Folder and Subfolders" not in html

    def test_subfolders_without_notes(self, client):
        top = NoteFolder.objects.create(name="Top")
        NoteFolder.objects.create(name="Mid", parent=top)
        html = client.get(
            reverse("notes:folder-delete-confirm", args=[top.id])
        ).content.decode()
        assert "This folder contains 1 subfolder." in html
        assert "note" not in html.split("modal-body")[1].split("modal-footer")[0]
        assert "Delete Folder and Subfolders" in html

    def test_folder_with_only_its_own_notes(self, client, user):
        folder = NoteFolder.objects.create(name="Flat")
        Note.objects.create(author=user, title="Only", folder=folder)
        html = client.get(
            reverse("notes:folder-delete-confirm", args=[folder.id])
        ).content.decode()
        assert "This folder contains 1 note." in html
        assert "subfolder" not in html.split("modal-body")[1].split("modal-footer")[0]

    def test_keep_notes_keeps_the_subfolders_notes_too(self, client, tree):
        resp = client.delete(reverse("notes:folder-delete", args=[tree.id]))
        assert resp.status_code == 204
        assert not NoteFolder.objects.filter(name="Top").exists()
        mid = NoteFolder.objects.get(name="Mid")
        assert mid.parent_id is None
        assert Note.objects.filter(title__in=["One", "Two", "Three"]).count() == 3
