"""The inline Practice Area menu on an intake can clear the area as well as
set it: it offered only the active areas, so an area set by mistake could
only be changed through the full edit form."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _cell(client, intake):
    return client.get(f"/intakes/{intake.id}/").content.decode()


def test_the_menu_offers_none_while_an_area_is_set(client, intake):
    body = _cell(client, intake)

    assert reverse("intakes:clear-practice-area", kwargs={"pk": intake.id}) in body


def test_the_menu_offers_no_none_when_the_area_is_already_empty(client, intake):
    intake.practice_area = None
    intake.save()

    body = _cell(client, intake)

    assert reverse("intakes:clear-practice-area", kwargs={"pk": intake.id}) not in body


def test_choosing_none_clears_the_area(client, intake):
    response = client.post(
        reverse("intakes:clear-practice-area", kwargs={"pk": intake.id})
    )

    assert response.status_code == 200
    intake.refresh_from_db()
    assert intake.practice_area is None
    assert "—" in response.content.decode()


def test_a_link_cannot_clear_the_area(client, intake):
    response = client.get(
        reverse("intakes:clear-practice-area", kwargs={"pk": intake.id})
    )

    assert response.status_code == 405
    intake.refresh_from_db()
    assert intake.practice_area is not None
