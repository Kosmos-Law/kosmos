"""Tests for the practice-wide search JSON API behind the Claude Desktop
MCP server's search_kosmos tool."""

import pytest
from django.test import Client

from apps.drafts.models import CompanionToken

pytestmark = pytest.mark.django_db


@pytest.fixture
def api(user):
    return Client(HTTP_X_KOSMOS_TOKEN=CompanionToken.for_user(user).key)


def search(api, **params):
    response = api.get("/search/api/", params)
    assert response.status_code == 200
    return response.json()


def test_missing_token_is_401():
    assert Client().get("/search/api/", {"q": "Gandhi"}).status_code == 401


def test_missing_query_is_400(api):
    assert api.get("/search/api/").status_code == 400


def test_unknown_scope_is_400(api):
    response = api.get("/search/api/", {"q": "x", "scope": "bogus"})
    assert response.status_code == 400
    assert "matters" in response.json()["error"]


def test_contacts_and_intakes(api, contact, intake):
    body = search(api, q="Gandhi")
    assert body["total"] == 2
    assert f"[contact:{contact.id}] Mohandas Gandhi (Gandhi, PC" in body["text"]
    assert f"[intake:{intake.id}]" in body["text"]


def test_scope_limits_results(api, contact, intake):
    body = search(api, q="Gandhi", scope="contacts")
    assert body["total"] == 1
    assert "Intakes" not in body["text"]


def test_intakes_need_permission(api, user, contact, intake):
    user.perm_intakes = False
    user.save()
    body = search(api, q="Gandhi")
    assert body["total"] == 1
    assert "[intake:" not in body["text"]


def test_case_number_finds_proceeding(api, proceeding):
    body = search(api, q="2024cv12345")
    assert f"[proceeding:{proceeding.id}] 2024-CV-12345" in body["text"]
    assert f"[matter:{proceeding.matter.id}]" in body["text"]


def test_digits_match_phone(api, contact):
    body = search(api, q="406")
    assert f"[contact:{contact.id}]" in body["text"]


def test_no_matches(api):
    body = search(api, q="zzzz-nothing")
    assert body["total"] == 0
    assert body["text"] == "No matches."
