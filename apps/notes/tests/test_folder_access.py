"""Who may see and change note folders, and what the editor's trees list.

A folder with no matter is the library's and open to every user. A folder
on a matter, and the notes in it, are for the people who may see that
matter: a user limited to assigned matters gets a 404 for another matter's
folder, the same answer as for a folder that does not exist.
"""

import pytest
from django.urls import reverse

from apps.notes.models import Note, NoteFolder, NoteView

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_folder(other_matter):
    return NoteFolder.objects.create(name="Privileged Strategy", matter=other_matter)


@pytest.fixture
def other_note(user, other_matter, other_folder):
    return Note.objects.create(
        author=user,
        matter=other_matter,
        folder=other_folder,
        title="Settlement Ceiling",
        content="Do not exceed.",
    )


@pytest.fixture
def own_folder(matter):
    return NoteFolder.objects.create(name="Own Folder", matter=matter)


@pytest.fixture
def library_note(user):
    return Note.objects.create(author=user, title="Library Note")


class TestEditorTree:
    def test_matters_pane_lists_only_the_users_matters(
        self, restricted_client, library_note, own_folder, other_note
    ):
        for url in (
            reverse("notes:note-view", args=[library_note.id]),
            reverse("notes:editor-file-tree") + f"?note={library_note.id}",
        ):
            html = restricted_client.get(url).content.decode()
            assert "Test Matter" in html
            assert "Own Folder" in html
            assert "Unassigned Matter" not in html
            assert "Privileged Strategy" not in html
            assert "Settlement Ceiling" not in html

    def test_all_matters_user_sees_every_open_matter(
        self, client, library_note, own_folder, other_note
    ):
        html = client.get(
            reverse("notes:editor-file-tree") + f"?note={library_note.id}"
        ).content.decode()
        assert "Test Matter" in html
        assert "Unassigned Matter" in html
        assert "Settlement Ceiling" in html

    def test_library_tree_is_shared(self, restricted_client, library_note):
        NoteFolder.objects.create(name="Firm Forms")
        html = restricted_client.get(
            reverse("notes:editor-file-tree") + f"?note={library_note.id}"
        ).content.decode()
        assert "Firm Forms" in html
        assert "Library Note" in html

    def test_recents_drop_a_note_the_user_can_no_longer_see(
        self, restricted_client, restricted, library_note, other_note
    ):
        # Viewed while still on the matter, then taken off it
        NoteView.objects.create(user=restricted, note=other_note)
        html = restricted_client.get(
            reverse("notes:note-view", args=[library_note.id])
        ).content.decode()
        assert "Settlement Ceiling" not in html

    def test_launch_does_not_land_on_a_note_the_user_can_no_longer_see(
        self, restricted_client, restricted, library_note, other_note
    ):
        NoteView.objects.create(user=restricted, note=library_note)
        NoteView.objects.create(user=restricted, note=other_note)  # most recent
        resp = restricted_client.get(reverse("notes:launch"))
        assert resp.status_code == 302
        assert resp.url == reverse("notes:note-view", args=[library_note.id])

        resp = restricted_client.get(
            reverse("notes:launch"), headers={"HX-Request": "true"}
        )
        assert resp.status_code == 200
        assert "Settlement Ceiling" not in resp.content.decode()
        assert "Do not exceed." not in resp.content.decode()


class TestFolderCreate:
    def test_cannot_create_at_another_matters_root(
        self, restricted_client, other_matter
    ):
        resp = restricted_client.post(
            reverse("notes:folder-add") + f"?matter={other_matter.id}"
        )
        assert resp.status_code == 404
        assert not NoteFolder.objects.filter(matter=other_matter).exists()

    def test_cannot_create_under_another_matters_folder(
        self, restricted_client, other_folder
    ):
        resp = restricted_client.post(
            reverse("notes:folder-add") + f"?parent={other_folder.id}"
        )
        assert resp.status_code == 404
        assert not NoteFolder.objects.filter(parent=other_folder).exists()

    def test_can_create_in_own_matter_and_in_the_library(
        self, restricted_client, matter, own_folder
    ):
        resp = restricted_client.post(
            reverse("notes:folder-add") + f"?matter={matter.id}"
        )
        assert resp.status_code == 204
        resp = restricted_client.post(
            reverse("notes:folder-add") + f"?parent={own_folder.id}"
        )
        assert resp.status_code == 204
        assert NoteFolder.objects.filter(parent=own_folder, matter=matter).exists()
        resp = restricted_client.post(reverse("notes:folder-add"))
        assert resp.status_code == 204
        assert NoteFolder.objects.filter(matter__isnull=True, name="Untitled").exists()


class TestAnotherMattersFolder:
    """Every folder view refuses a folder on a matter the user cannot see."""

    def test_rename(self, restricted_client, other_folder):
        resp = restricted_client.post(
            reverse("notes:folder-rename", args=[other_folder.id]), {"name": "Mine"}
        )
        assert resp.status_code == 404
        other_folder.refresh_from_db()
        assert other_folder.name == "Privileged Strategy"

    def test_edit_form_and_save(self, restricted_client, other_folder):
        url = reverse("notes:folder-edit", args=[other_folder.id])
        resp = restricted_client.get(url)
        assert resp.status_code == 404
        assert b"Privileged Strategy" not in resp.content
        resp = restricted_client.post(url, {"name": "Mine", "parent": ""})
        assert resp.status_code == 404
        other_folder.refresh_from_db()
        assert other_folder.name == "Privileged Strategy"

    def test_delete_confirm(self, restricted_client, other_folder, other_note):
        resp = restricted_client.get(
            reverse("notes:folder-delete-confirm", args=[other_folder.id])
        )
        assert resp.status_code == 404
        assert b"Privileged Strategy" not in resp.content

    def test_delete(self, restricted_client, other_folder, other_note):
        url = (
            reverse("notes:folder-delete", args=[other_folder.id])
            + "?delete_notes=true&delete_subfolders=true"
        )
        for send in (restricted_client.delete, restricted_client.post):
            assert send(url).status_code == 404
        assert NoteFolder.objects.filter(pk=other_folder.pk).exists()
        assert Note.objects.filter(pk=other_note.pk).exists()

    def test_reparent(self, restricted_client, other_matter, other_folder):
        child = NoteFolder.objects.create(
            name="Child", matter=other_matter, parent=other_folder
        )
        resp = restricted_client.post(
            reverse("notes:folder-reparent", args=[child.id]), {"destination": ""}
        )
        assert resp.status_code == 404
        child.refresh_from_db()
        assert child.parent_id == other_folder.id

    def test_reparent_into_it(self, restricted_client, own_folder, other_folder):
        resp = restricted_client.post(
            reverse("notes:folder-reparent", args=[own_folder.id]),
            {"destination": other_folder.id},
        )
        assert resp.status_code == 404
        own_folder.refresh_from_db()
        assert own_folder.parent_id is None

    def test_move_a_note_into_it(self, restricted_client, note, other_folder):
        resp = restricted_client.post(
            reverse("notes:note-move", args=[note.id]),
            {"destination": other_folder.id},
        )
        assert resp.status_code == 404
        note.refresh_from_db()
        assert note.folder_id is None

    def test_user_with_all_matters_is_not_refused(self, client, other_folder):
        resp = client.post(
            reverse("notes:folder-rename", args=[other_folder.id]), {"name": "Renamed"}
        )
        assert resp.status_code == 204


class TestFoldersTheUserMayChange:
    def test_own_matters_folder(self, restricted_client, own_folder):
        resp = restricted_client.post(
            reverse("notes:folder-rename", args=[own_folder.id]), {"name": "Renamed"}
        )
        assert resp.status_code == 204
        assert (
            restricted_client.get(
                reverse("notes:folder-edit", args=[own_folder.id])
            ).status_code
            == 200
        )
        assert (
            restricted_client.get(
                reverse("notes:folder-delete-confirm", args=[own_folder.id])
            ).status_code
            == 200
        )
        resp = restricted_client.delete(
            reverse("notes:folder-delete", args=[own_folder.id]) + "?context=editor"
        )
        assert resp.status_code == 204
        assert not NoteFolder.objects.filter(pk=own_folder.pk).exists()

    def test_library_folder(self, restricted_client):
        folder = NoteFolder.objects.create(name="Firm Forms")
        resp = restricted_client.post(
            reverse("notes:folder-rename", args=[folder.id]), {"name": "Forms"}
        )
        assert resp.status_code == 204
        folder.refresh_from_db()
        assert folder.name == "Forms"
