"""The first click on the column a list already starts sorted by reverses
it.

Timeline starts oldest first by Date and Time, Witnesses by Name A to Z.
The first click used to store that same order, so nothing changed until
the second click."""

import pytest

from apps.case.facts.sorting import toggled_sort_key
from apps.case.models import Fact, Witness

pytestmark = pytest.mark.django_db


def _facts(client, matter):
    response = client.get(f"/case/{matter.id}/facts/list/")
    return [fact.description for fact in response.context["facts"]]


def _witnesses(client, matter):
    response = client.get(f"/case/{matter.id}/witnesses/list/")
    return [witness.name for witness in response.context["witnesses"]]


def test_first_click_on_date_and_time_reverses_the_timeline(client, matter, user):
    for day, description in (("2024-01-01", "First"), ("2024-02-01", "Second")):
        Fact.objects.create(user=user, matter=matter, date=day, description=description)
    assert _facts(client, matter) == ["First", "Second"]

    client.get(f"/case/{matter.id}/facts/sort/date/")

    assert client.session[f"facts_filter_{matter.id}"]["order_by"] == "-date"
    assert _facts(client, matter) == ["Second", "First"]

    client.get(f"/case/{matter.id}/facts/sort/date/")

    assert _facts(client, matter) == ["First", "Second"]


def test_first_click_on_name_reverses_the_witnesses(client, matter, user):
    for name in ("Able", "Baker"):
        Witness.objects.create(user=user, matter=matter, name=name, created_by=user)
    assert _witnesses(client, matter) == ["Able", "Baker"]

    client.get(f"/case/{matter.id}/witnesses/sort/name/")

    assert client.session[f"witnesses_filter_{matter.id}"]["order_by"] == "-name"
    assert _witnesses(client, matter) == ["Baker", "Able"]

    client.get(f"/case/{matter.id}/witnesses/sort/name/")

    assert _witnesses(client, matter) == ["Able", "Baker"]


def test_a_stored_sort_from_another_column_is_not_the_default(client, matter, user):
    """After sorting by importance, a click on Name sorts by Name A to Z."""
    Witness.objects.create(user=user, matter=matter, name="Able", created_by=user)
    client.get(f"/case/{matter.id}/witnesses/sort/-importance/")

    client.get(f"/case/{matter.id}/witnesses/sort/name/")

    assert client.session[f"witnesses_filter_{matter.id}"]["order_by"] == "name"


def test_toggled_sort_key():
    keys = {"name", "-name", "-importance", "importance"}

    assert toggled_sort_key({}, keys, "name", "name") == "-name"
    assert toggled_sort_key({"order_by": "-name"}, keys, "name", "name") == "name"
    assert toggled_sort_key({"order_by": "name"}, keys, "name", "-importance") == (
        "-importance"
    )
    assert toggled_sort_key(
        {"order_by": "-importance"}, keys, "name", "-importance"
    ) == ("importance")
    # A stored key the list does not know counts as the default.
    assert toggled_sort_key({"order_by": "bogus"}, keys, "name", "name") == "-name"
