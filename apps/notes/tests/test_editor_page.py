"""What the editor page gives its scripts and says to its users.

The behaviour these pieces drive is in static/js/notes (see tests/js); the
tests here pin the server's half: the hooks the scripts look for, and the
wording.
"""

import pytest
from django.urls import reverse

from apps.notes.models import Note

pytestmark = pytest.mark.django_db


@pytest.fixture
def library_note(user):
    return Note.objects.create(author=user, title="Library Note")


class TestNewNoteButton:
    """The button sits in a bar rendered once per page load, so it carries no
    address of its own: the script reads the scope from the open note."""

    def test_button_has_no_baked_in_scope(self, client, note):
        html = client.get(reverse("notes:note-view", args=[note.id])).content.decode()
        button = html.split('id="new-note-btn"')[0].rsplit("<a", 1)[1]
        button += html.split('id="new-note-btn"')[1].split(">", 1)[0]
        assert "hx-post" not in button
        assert f'data-library-add-url="{reverse("notes:add")}"' in button

    def test_each_note_names_where_a_new_note_goes(self, client, note, library_note):
        matter_add = reverse("case:notes-add", args=[note.matter_id])
        library_add = reverse("notes:add")
        for name in ("notes:note-view", "notes:note-content-partial"):
            html = client.get(reverse(name, args=[note.id])).content.decode()
            assert f'noteAddUrl: "{matter_add}"' in html
            html = client.get(reverse(name, args=[library_note.id])).content.decode()
            assert f'noteAddUrl: "{library_add}"' in html


class TestShortcutsDialog:
    def test_the_menu_item_the_shortcut_clicks_exists(self, client, note):
        html = client.get(reverse("notes:note-view", args=[note.id])).content.decode()
        item = html.split('id="shortcuts-btn"')[1].split(">", 1)[0]
        assert f'hx-get="{reverse("notes:notes-shortcuts")}"' in item

    def test_dialog_lists_search_and_both_delete_block_keys(self, client):
        html = client.get(reverse("notes:notes-shortcuts")).content.decode()
        rows = [" ".join(row.split()) for row in html.split("<tr>")]
        assert any("<kbd>K</kbd>" in row and "Search notes" in row for row in rows)
        assert any(
            "<kbd>D</kbd>" in row
            and "<kbd>Delete</kbd>" in row
            and "Delete block" in row
            for row in rows
        )
        assert any("<kbd>?</kbd>" in row and "Show shortcuts" in row for row in rows)


class TestConflictBanner:
    def test_banner_covers_saves_by_other_people_and_the_ai(self, client, note):
        html = client.get(
            reverse("notes:note-content-partial", args=[note.id])
        ).content.decode()
        banner = html.split('id="note-conflict-banner"')[1].split("</div>")[0]
        assert "another person" in banner
        assert "the AI" in banner
        assert "Editing is paused." in banner
        assert "—" not in banner
