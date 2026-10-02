"""Deleting an intake deletes its notes. The database only detaches them,
which left every deleted intake's notes stored with no intake and no screen
that could reach them.
"""

import pytest

from apps.intakes.models import Intake, Note

pytestmark = pytest.mark.django_db


def test_deleting_an_intake_deletes_its_notes(client, user, intake, note):
    second = Note.objects.create(
        user=user, intake=intake, date="2024-03-01", type="Comment", details="x"
    )

    response = client.post(f"/intakes/{intake.id}/delete")

    assert response.status_code == 302
    assert not Intake.objects.filter(pk=intake.pk).exists()
    assert not Note.objects.filter(pk__in=[note.pk, second.pk]).exists()


def test_another_intakes_notes_are_untouched(client, user, intake, note):
    other = Intake.objects.create(name="Someone Else", date="2024-03-01")
    kept = Note.objects.create(
        user=user, intake=other, date="2024-03-01", type="Comment", details="x"
    )

    client.post(f"/intakes/{intake.id}/delete")

    assert Note.objects.filter(pk=kept.pk).exists()


def test_the_confirmation_says_the_notes_go_too(client, intake):
    body = client.get(f"/intakes/{intake.id}/edit").content.decode()

    assert "Delete this intake and its notes?" in body
