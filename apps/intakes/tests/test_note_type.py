"""Editing a note keeps its type. A note filed by the system ("Client Form")
has a type the Type dropdown does not list, so the form showed the first
option and saving the note retyped it "Call In".
"""

import pytest

from apps.intakes.forms import NoteForm
from apps.intakes.models import Note

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_form_note(user, intake):
    return Note.objects.create(
        user=user,
        intake=intake,
        date="2024-03-01",
        time="09:30",
        type="Client Form",
        details="**Property address**\n\n225 Paper Street",
    )


def _selected(html):
    """The option the Type select shows as chosen."""
    return html.split(" selected>", 1)[1].split("<", 1)[0]


def test_the_edit_form_shows_the_notes_own_type(client, client_form_note):
    response = client.get(f"/intakes/{client_form_note.id}/edit-note")

    assert _selected(str(response.context["form"]["type"])) == "Client Form"


def test_the_type_survives_an_edit(client, client_form_note):
    form = NoteForm(instance=client_form_note)
    data = {
        "date": "2024-03-01",
        "time": "09:30",
        # What the browser sends back: the option the select was showing.
        "type": _selected(str(form["type"])),
        "details": "Corrected by staff.",
    }

    response = client.post(f"/intakes/{client_form_note.id}/edit-note", data)

    assert response.status_code == 204
    client_form_note.refresh_from_db()
    assert client_form_note.type == "Client Form"
    assert client_form_note.details == "Corrected by staff."


def test_a_new_note_is_not_offered_system_types():
    form = NoteForm()

    assert "Client Form" not in str(form["type"])
    assert _selected(str(form["type"])) == "Comment"


def test_an_ordinary_note_keeps_the_usual_list(user, intake):
    note = Note.objects.create(
        user=user, intake=intake, date="2024-03-01", type="Email In"
    )

    form = NoteForm(instance=note)

    assert _selected(str(form["type"])) == "Email In"
    assert len(form.fields["type"].widget.choices) == len(NoteForm.Meta.TYPES)
