"""Deleting a note folder must take more than following a link.

The delete takes a folder tree and its notes with it, so a GET (a link, a
prefetch, an image tag on another site) must never do it.
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


class TestDeleteNeedsMoreThanALink:
    def test_get_deletes_nothing(self, client, tree):
        url = (
            reverse("notes:folder-delete", args=[tree.id])
            + "?delete_notes=true&delete_subfolders=true"
        )
        resp = client.get(url)
        assert resp.status_code == 405
        assert NoteFolder.objects.filter(name__in=["Top", "Mid", "Deep"]).count() == 3
        assert Note.objects.filter(title__in=["One", "Two", "Three"]).count() == 3

    @pytest.mark.parametrize("method", ["delete", "post"])
    def test_delete_and_post_do(self, client, tree, method):
        url = (
            reverse("notes:folder-delete", args=[tree.id])
            + "?delete_notes=true&delete_subfolders=true"
        )
        resp = getattr(client, method)(url)
        assert resp.status_code == 204
        assert not NoteFolder.objects.filter(name__in=["Top", "Mid", "Deep"]).exists()
        assert not Note.objects.filter(title__in=["One", "Two", "Three"]).exists()

    def test_the_dialog_sends_delete(self, client, tree):
        html = client.get(
            reverse("notes:folder-delete-confirm", args=[tree.id])
        ).content.decode()
        assert "hx-delete=" in html
        assert "hx-get=" not in html
