"""Deleting an intake or a note, and changing an intake's status, importance
or practice area, take a POST. A plain link (in an email, on another site)
sends a GET and must change nothing.
"""

import pytest

from apps.intakes.models import Intake, Note
from apps.matters.models import PracticeArea

pytestmark = pytest.mark.django_db


def test_a_link_cannot_delete_an_intake(client, intake):
    response = client.get(f"/intakes/{intake.id}/delete")

    assert response.status_code == 405
    assert Intake.objects.filter(pk=intake.pk).exists()


def test_the_delete_button_sends_a_post(client, intake):
    body = client.get(f"/intakes/{intake.id}/edit").content.decode()

    button = body.split(f'data-href="/intakes/{intake.id}/delete"', 1)[1]
    assert 'data-method="post"' in button.split(">", 1)[0]


def test_a_link_cannot_delete_a_note(client, note):
    response = client.get(f"/intakes/{note.id}/delete-note")

    assert response.status_code == 405
    assert Note.objects.filter(pk=note.pk).exists()


def test_a_link_cannot_change_the_status(client, intake):
    response = client.get(f"/intakes/edit-status/{intake.id}/Accepted")

    assert response.status_code == 405
    intake.refresh_from_db()
    assert intake.status == "Open"


def test_a_link_cannot_change_the_importance(client, intake):
    response = client.get(f"/intakes/edit-importance/{intake.id}/7")

    assert response.status_code == 405
    intake.refresh_from_db()
    assert intake.importance == 4


def test_a_link_cannot_change_the_practice_area(client, intake):
    title = PracticeArea.objects.create(name="Title", is_active=True)

    response = client.get(f"/intakes/edit-practice-area/{intake.id}/{title.id}")

    assert response.status_code == 405
    intake.refresh_from_db()
    assert intake.practice_area != title


def test_posts_still_change_them(client, intake):
    status = client.post(f"/intakes/edit-status/{intake.id}/Referred Out")
    importance = client.post(f"/intakes/edit-importance/{intake.id}/6")

    assert (status.status_code, importance.status_code) == (200, 204)
    intake.refresh_from_db()
    assert (intake.status, intake.importance) == ("Referred Out", 6)


def test_a_status_that_is_not_offered_is_refused(client, intake):
    response = client.post(f"/intakes/edit-status/{intake.id}/Whatever")

    assert response.status_code == 400
    intake.refresh_from_db()
    assert intake.status == "Open"
