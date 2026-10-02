"""The intake's click-to-edit Value and its importance flag take only what
the intake can hold. Text that is not a number used to be a server error on
Value, and the importance address took any number at all.
"""

import json

import pytest

pytestmark = pytest.mark.django_db


def _toast(response):
    return json.loads(response.headers["HX-Toast"])["message"]


@pytest.fixture
def valued(intake):
    intake.value = 250000
    intake.save()
    return intake


# -----------------------------------------------------
# value
# -----------------------------------------------------
def test_a_link_cannot_wipe_the_value(client, valued):
    response = client.get(f"/intakes/{valued.id}/value-update/")

    assert response.status_code == 405
    valued.refresh_from_db()
    assert valued.value == 250000


@pytest.mark.parametrize("typed", ["about 300k", "300,000", "1500.50", "9" * 12])
def test_a_value_that_is_not_a_whole_number_is_refused(client, valued, typed):
    response = client.post(f"/intakes/{valued.id}/value-update/", {"value": typed})

    assert response.status_code == 200
    assert "whole number" in _toast(response)
    # The display comes back showing the value that was kept.
    assert "$250,000" in response.content.decode()
    valued.refresh_from_db()
    assert valued.value == 250000


def test_a_number_is_saved(client, valued):
    response = client.post(f"/intakes/{valued.id}/value-update/", {"value": " 310000 "})

    assert response.status_code == 200
    assert "HX-Toast" not in response.headers
    assert "$310,000" in response.content.decode()
    valued.refresh_from_db()
    assert valued.value == 310000


def test_an_empty_value_clears_it(client, valued):
    client.post(f"/intakes/{valued.id}/value-update/", {"value": ""})

    valued.refresh_from_db()
    assert valued.value is None


# -----------------------------------------------------
# importance
# -----------------------------------------------------
@pytest.mark.parametrize("importance", [0, 8, 99])
def test_importance_outside_one_to_seven_is_refused(client, intake, importance):
    response = client.post(f"/intakes/edit-importance/{intake.id}/{importance}")

    assert response.status_code == 400
    intake.refresh_from_db()
    assert intake.importance == 4


@pytest.mark.parametrize("importance", [1, 7])
def test_importance_at_either_end_is_accepted(client, intake, importance):
    response = client.post(f"/intakes/edit-importance/{intake.id}/{importance}")

    assert response.status_code == 204
    intake.refresh_from_db()
    assert intake.importance == importance
