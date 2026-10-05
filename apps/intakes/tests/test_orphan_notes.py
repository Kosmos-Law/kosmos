"""Notes left behind by intakes deleted before the delete view removed their
notes: Note.intake is SET_NULL, so they survive with no intake. Opening one
to edit was a server error, and clean_intake_notes removes them."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.intakes.models import Note

pytestmark = pytest.mark.django_db


@pytest.fixture
def orphan(user):
    return Note.objects.create(
        user=user, intake=None, date="2022-12-28", type="General", details="lost"
    )


def test_editing_an_orphan_note_is_not_found_rather_than_an_error(client, orphan):
    response = client.get(f"/intakes/{orphan.id}/edit-note")

    assert response.status_code == 404


def test_the_command_only_reports_by_default(orphan, note):
    out = StringIO()

    call_command("clean_intake_notes", stdout=out)

    assert f"ID={orphan.id}" in out.getvalue()
    assert "Nothing deleted" in out.getvalue()
    assert Note.objects.filter(pk=orphan.pk).exists()


def test_the_command_deletes_only_orphans_with_apply(orphan, note):
    out = StringIO()

    call_command("clean_intake_notes", "--apply", stdout=out)

    assert "Deleted 1 orphan note(s)." in out.getvalue()
    assert not Note.objects.filter(pk=orphan.pk).exists()
    assert Note.objects.filter(pk=note.pk).exists()


def test_the_command_says_when_there_is_nothing_to_do(note):
    out = StringIO()

    call_command("clean_intake_notes", "--apply", stdout=out)

    assert "No orphan intake notes found." in out.getvalue()
    assert Note.objects.filter(pk=note.pk).exists()
