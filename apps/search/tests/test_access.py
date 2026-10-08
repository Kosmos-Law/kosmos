"""Search shows a user only what that user may open."""

import pytest
from django.test import Client
from watson import search as watson

from apps.accounts.models import CustomUser
from apps.intakes.models import Intake
from apps.matters.models import Matter
from apps.matters.proceedings.models import Proceeding

pytestmark = pytest.mark.django_db


def _client(**user_fields):
    user = CustomUser.objects.create(username="Rae", **user_fields)
    user.set_password("clawboy")
    user.save()
    client = Client()
    client.force_login(user)
    client.get("/dash/")
    return client, user


def _search(client, text, scope="all"):
    response = client.post("/search/results", {"search_text": text, "scope": scope})
    return response.context


@pytest.fixture
def matters():
    with watson.update_index():
        mine = Matter.objects.create(
            name="Quillfeather Assigned", status="Open", client_reference_id="7001"
        )
        theirs = Matter.objects.create(
            name="Quillfeather Unassigned", status="Open", client_reference_id="7002"
        )
    for matter, number in ((mine, "24-CV-0001"), (theirs, "24-CV-0002")):
        Proceeding.objects.create(
            matter=matter,
            date_filed="2024-01-02",
            forum="Example Superior",
            case_number=number,
            status="Ongoing",
        )
    return mine, theirs


def test_restricted_user_finds_only_assigned_matters(matters):
    mine, theirs = matters
    client, user = _client(perm_all_matters=False)
    mine.members.add(user)

    by_name = _search(client, "Quillfeather")
    by_reference = _search(client, "7002")
    by_case_number = _search(client, "24-CV-000")

    assert by_name["matters"] == [mine]
    assert by_reference["matters"] == []
    assert [p.matter for p in by_case_number["proceedings"]] == [mine]


def test_unrestricted_user_finds_every_matter(matters):
    client, _user = _client()

    found = _search(client, "Quillfeather")["matters"]

    assert set(found) == set(matters)


def test_intakes_need_the_intakes_permission():
    with watson.update_index():
        Intake.objects.create(name="Quillfeather Prospect", phone="4045550100")
    client, _user = _client(perm_intakes=False)

    by_name = _search(client, "Quillfeather")
    by_phone = _search(client, "4045550100", scope="intakes")
    tabs = [key for key, _label, _model in by_name["scopes"]]

    assert by_name["intakes"] == []
    assert by_phone["intakes"] == []
    assert "intakes" not in tabs
    assert b'data-scope="intakes"' not in client.get("/search/").content
