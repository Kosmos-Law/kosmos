"""The flag column's sort button. It posted a sort the filter did not know:
nothing was sorted, the value stayed in the session, and the Filter dialog
opened on a validation error from then on.
"""

import pytest

from apps.intakes.models import Intake

pytestmark = pytest.mark.django_db


@pytest.fixture
def intakes():
    def make(name, importance, date):
        return Intake.objects.create(
            name=name, importance=importance, date=date, status="Open"
        )

    return {
        "low": make("Low", 2, "2024-01-03"),
        "high": make("High", 7, "2024-01-01"),
        "normal_old": make("Normal, older", 4, "2024-01-02"),
        "normal_new": make("Normal, newer", 4, "2024-01-04"),
    }


def _names(client):
    response = client.get("/intakes/list/")
    return [intake.name for intake in response.context["intakes"]]


def test_the_flag_button_sorts_by_importance(client, intakes):
    response = client.post("/intakes/order-by/-importance")

    assert response.status_code == 204
    # Highest first; equal importance falls back to newest first.
    assert _names(client) == ["High", "Normal, newer", "Normal, older", "Low"]


def test_the_flag_button_lights_up(client, intakes):
    client.post("/intakes/order-by/-importance")

    response = client.get("/intakes/list/")

    assert response.context["current_order"] == "importance"


def test_the_filter_dialog_still_opens_clean(client, intakes):
    client.get("/intakes/list/")
    client.post("/intakes/order-by/-importance")

    response = client.get("/intakes/filter-intakes")

    form = response.context["filter"].form
    assert form.is_valid(), form.errors
    assert form["order_by"].value() == ["-importance"]


def test_an_unknown_sort_is_refused_and_not_kept(client, intakes):
    client.get("/intakes/list/")

    response = client.post("/intakes/order-by/-nonsense")

    assert response.status_code == 400
    assert client.session["intake_filter"].get("order_by") == "-date"


def test_date_and_name_still_sort(client, intakes):
    client.post("/intakes/order-by/name")
    by_name = _names(client)
    client.post("/intakes/order-by/date")
    by_date = _names(client)

    assert by_name == ["High", "Low", "Normal, newer", "Normal, older"]
    assert by_date == ["High", "Normal, older", "Low", "Normal, newer"]


def test_a_second_click_on_the_flag_reverses_the_sort(client, intakes):
    client.post("/intakes/order-by/-importance")
    client.post("/intakes/order-by/-importance")

    assert client.session["intake_filter"]["order_by"] == "importance"
    # Lowest first; equal importance still falls back to newest first.
    assert _names(client) == ["Low", "Normal, newer", "Normal, older", "High"]


def test_a_third_click_on_the_flag_restores_the_first_sort(client, intakes):
    for _ in range(3):
        client.post("/intakes/order-by/-importance")

    assert client.session["intake_filter"]["order_by"] == "-importance"
