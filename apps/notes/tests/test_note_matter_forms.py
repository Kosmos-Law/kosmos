"""The two forms that show a note's matter: Edit Details on the matter Notes
tab and Note Properties in the editor.

Both list open matters. A note on a matter that is not Open must still show
its own matter, selected: otherwise Edit Details cannot save a plain rename
and Properties would send the note to whichever open matter is listed first.
"""

import pytest
from django.urls import reverse

from apps.matters.models import Matter
from apps.notes.models import Note, NoteFolder

pytestmark = pytest.mark.django_db


@pytest.fixture
def closed_matter(practice_area):
    matter = Matter.objects.create(
        name="Closed Matter", status="Open", practice_area=practice_area
    )
    # Straight to the column: closing through save() runs the archival steps
    Matter.objects.filter(pk=matter.pk).update(status="Closed")
    matter.refresh_from_db()
    return matter


@pytest.fixture
def closed_note(user, closed_matter):
    folder = NoteFolder.objects.create(name="Kept", matter=closed_matter)
    return Note.objects.create(
        author=user, matter=closed_matter, folder=folder, title="Old Title"
    )


class TestEditDetails:
    def test_form_opens_on_the_notes_own_matter(self, client, matter, closed_note):
        html = client.get(reverse("case:notes-edit", args=[closed_note.id])).content
        assert f'<option value="{closed_note.matter_id}" selected'.encode() in html
        # Open matters are still offered; no blank choice to fall into
        assert f'<option value="{matter.id}"'.encode() in html
        assert b'<option value=""' not in html

    def test_rename_on_a_closed_matter(self, client, closed_matter, closed_note):
        resp = client.post(
            reverse("case:notes-edit", args=[closed_note.id]),
            {"matter": closed_matter.id, "category": "note", "title": "New Title"},
        )
        assert resp.status_code == 204
        closed_note.refresh_from_db()
        assert closed_note.title == "New Title"
        assert closed_note.matter_id == closed_matter.id
        assert closed_note.folder is not None  # same matter: stays in its folder

    def test_blank_matter_is_a_form_error_not_a_server_error(
        self, client, closed_matter, closed_note
    ):
        resp = client.post(
            reverse("case:notes-edit", args=[closed_note.id]),
            {"matter": "", "category": "note", "title": "New Title"},
        )
        assert resp.status_code == 200
        closed_note.refresh_from_db()
        assert closed_note.title == "Old Title"
        assert closed_note.matter_id == closed_matter.id

    def test_choices_are_limited_to_the_users_matters(
        self, restricted_client, note, other_matter
    ):
        html = restricted_client.get(reverse("case:notes-edit", args=[note.id])).content
        assert f'<option value="{note.matter_id}" selected'.encode() in html
        assert b"Unassigned Matter" not in html
        resp = restricted_client.post(
            reverse("case:notes-edit", args=[note.id]),
            {"matter": other_matter.id, "category": "note", "title": "Moved"},
        )
        assert resp.status_code == 200
        note.refresh_from_db()
        assert note.matter_id != other_matter.id

    def test_moving_to_another_open_matter_still_works(
        self, client, matter, closed_note
    ):
        resp = client.post(
            reverse("case:notes-edit", args=[closed_note.id]),
            {"matter": matter.id, "category": "note", "title": "Old Title"},
        )
        assert resp.status_code == 204
        closed_note.refresh_from_db()
        assert closed_note.matter_id == matter.id
        assert closed_note.folder is None  # folders belong to one matter's tree


class TestNoteProperties:
    def test_menu_opens_on_the_notes_own_matter(self, client, matter, closed_note):
        html = client.get(
            reverse("notes:note-properties", args=[closed_note.id])
        ).content.decode()
        assert f'<option value="{closed_note.matter_id}" selected>' in html
        assert html.count(" selected>") == 1
        assert f'<option value="{matter.id}" >' in html

    def test_move_to_the_same_matter_does_nothing(
        self, client, closed_matter, closed_note
    ):
        folder_id = closed_note.folder_id
        resp = client.post(
            reverse("notes:note-reassign-matter", args=[closed_note.id]),
            {"matter": closed_matter.id},
        )
        assert resp.status_code == 204
        closed_note.refresh_from_db()
        assert closed_note.matter_id == closed_matter.id
        assert closed_note.folder_id == folder_id

    def test_move_to_an_open_matter(self, client, matter, closed_note):
        resp = client.post(
            reverse("notes:note-reassign-matter", args=[closed_note.id]),
            {"matter": matter.id},
        )
        assert resp.status_code == 204
        closed_note.refresh_from_db()
        assert closed_note.matter_id == matter.id
        assert closed_note.folder is None

    def test_cannot_move_onto_some_other_closed_matter(
        self, client, note, closed_matter
    ):
        resp = client.post(
            reverse("notes:note-reassign-matter", args=[note.id]),
            {"matter": closed_matter.id},
        )
        assert resp.status_code == 404
        note.refresh_from_db()
        assert note.matter_id != closed_matter.id

    def test_missing_or_bad_matter_is_refused(self, client, note):
        for value in ("", "abc"):
            resp = client.post(
                reverse("notes:note-reassign-matter", args=[note.id]), {"matter": value}
            )
            assert resp.status_code == 404

    def test_cannot_move_onto_a_matter_the_user_cannot_see(
        self, restricted_client, note, other_matter
    ):
        html = restricted_client.get(
            reverse("notes:note-properties", args=[note.id])
        ).content
        assert b"Unassigned Matter" not in html
        resp = restricted_client.post(
            reverse("notes:note-reassign-matter", args=[note.id]),
            {"matter": other_matter.id},
        )
        assert resp.status_code == 404
