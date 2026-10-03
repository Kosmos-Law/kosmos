"""A list's sort key comes from the URL, is kept in the session and
reaches the query, so only the list's own keys are taken.

A key that is not one of them answers 400 and is not stored. A bad key
already in a session (from before the check, or posted through a filter
dialog) no longer breaks the list: it is ignored and the list shows in
its default order. On Full Cases such a key used to make every load of
the list a server error for that user and matter."""

import pytest

from apps.case.models import CaseLaw, Witness

pytestmark = pytest.mark.django_db

# tab, sort address, session key prefix, a key the list accepts
LISTS = [
    ("facts", "facts/sort", "facts_filter", "description"),
    ("witnesses", "witnesses/sort", "witnesses_filter", "affiliation"),
    ("highlights", "highlights/filter/sort", "highlights_filter", "slug"),
    ("caselaws", "caselaws/sort", "caselaws_filter", "case_name"),
]
BAD_KEYS = ["password", "matter__name", "--importance", "created_by__password"]


@pytest.fixture
def rows(matter, user, fact, highlight):
    Witness.objects.create(user=user, matter=matter, name="Dr. Alice Reed")
    CaseLaw.objects.create(
        matter=matter, case_name="Roe v. Wade", citation="410 U.S. 113"
    )


def _store(client, matter, prefix, order_by):
    session = client.session
    session[f"{prefix}_{matter.id}"] = {"order_by": order_by}
    session.save()


@pytest.mark.parametrize("tab, sort_path, prefix, good", LISTS)
def test_an_unknown_key_is_refused_and_not_stored(
    client, matter, rows, tab, sort_path, prefix, good
):
    for bad in BAD_KEYS:
        response = client.get(f"/case/{matter.id}/{sort_path}/{bad}/")

        assert response.status_code == 400, bad
        assert f"{prefix}_{matter.id}" not in client.session, bad


@pytest.mark.parametrize("tab, sort_path, prefix, good", LISTS)
def test_the_lists_own_key_is_taken(client, matter, rows, tab, sort_path, prefix, good):
    response = client.get(f"/case/{matter.id}/{sort_path}/{good}/")

    assert response.status_code in (204, 302)
    assert client.session[f"{prefix}_{matter.id}"]["order_by"].lstrip("-") == good
    assert client.get(f"/case/{matter.id}/{tab}/list/").status_code == 200


@pytest.mark.parametrize("tab, sort_path, prefix, good", LISTS)
@pytest.mark.parametrize("bad", BAD_KEYS + [["password"], 7])
def test_a_bad_key_already_stored_does_not_break_the_list(
    client, matter, rows, tab, sort_path, prefix, good, bad
):
    _store(client, matter, prefix, bad)

    response = client.get(f"/case/{matter.id}/{tab}/list/")

    assert response.status_code == 200
    rows_key = {
        "facts": "facts",
        "witnesses": "witnesses",
        "highlights": "highlights",
        "caselaws": "case_laws",
    }[tab]
    assert len(response.context[rows_key]) == 1


def test_a_bad_stored_key_falls_back_to_each_lists_default_order(
    client, matter, user, rows
):
    for tab, _, prefix, _ in LISTS:
        _store(client, matter, prefix, "password")
    expected = {
        "facts": "date",
        "witnesses": "name",
        "highlights": "-created",
        "caselaws": "-created_at",
    }

    for tab, default in expected.items():
        response = client.get(f"/case/{matter.id}/{tab}/list/")
        assert response.context["current_order"] == default, tab


def test_a_bad_stored_key_keeps_the_rest_of_the_filter(client, matter, user, fact):
    session = client.session
    session[f"facts_filter_{matter.id}"] = {
        "order_by": "password",
        "keyword": "no such fact",
    }
    session.save()

    response = client.get(f"/case/{matter.id}/facts/list/")

    assert list(response.context["facts"]) == []


def test_full_cases_takes_only_the_bare_column_name(client, matter, rows):
    """The header sends the column; the list chooses the direction."""
    response = client.get(f"/case/{matter.id}/caselaws/sort/-case_name/")

    assert response.status_code == 400
