"""The structured matters API (apps/matters/api.py): the token check, the
fields, every status, the per-user limit, and a matter's proceedings."""

import pytest
from django.test import Client

from apps.accounts.models import ApiToken, CustomUser
from apps.matters.models import Matter
from apps.matters.proceedings.models import Proceeding
from apps.mcp.models import RESOURCE_MATTERS, McpClient, McpConnection, McpToken

pytestmark = pytest.mark.django_db


@pytest.fixture
def api(user):
    return Client(HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(user).key)


@pytest.fixture
def outsider():
    return CustomUser.objects.create(
        username="matters-outsider",
        email="matters-outsider@example.com",
        user_rate=100,
        perm_all_matters=False,
    )


def test_the_api_wants_a_token(client, matter):
    # A signed-in session is not a token.
    assert client.get("/matters/api/").status_code == 401
    assert client.get(f"/matters/api/{matter.id}/").status_code == 401
    assert Client(HTTP_X_KOSMOS_TOKEN="nope").get("/matters/api/").status_code == 401


def test_the_list_gives_every_status_in_fields(api, user, matter):
    Matter.objects.create(user=user, name="Closed Matter", status="Closed")
    matters = api.get("/matters/api/").json()["matters"]
    assert [m["name"] for m in matters] == ["Closed Matter", "Sample Test Matter"]
    closed, sample = matters
    assert closed["status"] == "Closed"
    assert closed["client"] == "" and closed["date_start"] is None
    assert sample["id"] == matter.id
    assert sample["status"] == "Open"
    assert sample["client"] == matter.client.name
    assert sample["client_reference_id"] == "125"
    assert sample["practice_area"] == matter.practice_area.name
    assert sample["date_start"] == "2020-08-07"
    assert sample["url"] == f"http://testserver/matters/{matter.id}"


def test_the_list_narrows_by_q_and_status(api, user, matter):
    Matter.objects.create(user=user, name="Closed Matter", status="Closed")

    def names(query):
        return [m["name"] for m in api.get(f"/matters/api/?{query}").json()["matters"]]

    assert names("q=closed") == ["Closed Matter"]
    assert names("q=125") == ["Sample Test Matter"]  # the client reference
    assert names(f"q={matter.client.name}") == ["Sample Test Matter"]
    assert names("status=Closed") == ["Closed Matter"]
    assert names("status=Open&status=Closed") == [
        "Closed Matter",
        "Sample Test Matter",
    ]
    assert names("q=nothing-like-this") == []


def test_a_limited_user_gets_only_their_matters(outsider, matter, user):
    api = Client(HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(outsider).key)
    assert api.get("/matters/api/").json()["matters"] == []
    assert api.get(f"/matters/api/{matter.id}/").status_code == 404
    matter.members.add(outsider)
    assert [m["id"] for m in api.get("/matters/api/").json()["matters"]] == [matter.id]
    assert api.get(f"/matters/api/{matter.id}/").status_code == 200


def test_a_matter_comes_with_its_proceedings_primary_first(api, user, matter):
    Proceeding.objects.create(
        user=user,
        matter=matter,
        date_filed="2019-01-02",
        forum="Fulton Superior",
        case_number="19CV1",
        status="Concluded",
    )
    primary = Proceeding.objects.create(
        user=user,
        matter=matter,
        date_filed="2021-03-04",
        forum="N.D. Ga.",
        case_number="1:21-cv-00042",
        nickname="Federal case",
        status="Ongoing",
        primary=True,
    )
    data = api.get(f"/matters/api/{matter.id}/").json()
    assert data["matter"]["id"] == matter.id
    assert data["matter"]["name"] == "Sample Test Matter"
    assert [p["case_number"] for p in data["proceedings"]] == [
        "1:21-cv-00042",
        "19CV1",
    ]
    assert data["proceedings"][0] == {
        "id": primary.id,
        "forum": "N.D. Ga.",
        "case_number": "1:21-cv-00042",
        "nickname": "Federal case",
        "date_filed": "2021-03-04",
        "status": "Ongoing",
        "primary": True,
    }
    assert data["proceedings"][1]["nickname"] == ""


def test_a_closed_matter_is_still_readable(api, user):
    closed = Matter.objects.create(user=user, name="Closed Matter", status="Closed")
    data = api.get(f"/matters/api/{closed.id}/").json()
    assert data["matter"]["status"] == "Closed" and data["proceedings"] == []


def test_the_api_is_read_only_and_404s_an_unknown_matter(api, matter):
    assert api.post("/matters/api/").status_code == 405
    assert api.post(f"/matters/api/{matter.id}/").status_code == 405
    response = api.get("/matters/api/999999/")
    assert response.status_code == 404 and "error" in response.json()


# ------------------------------------------- the bearer (how Discover connects)


@pytest.fixture
def bearer(user):
    """A client holding an access token issued for the matters API."""
    oauth_client = McpClient.objects.create(
        client_id="discover-test",
        name="Kosmos Discover",
        redirect_uris=["https://discover.example.com/kosmos/callback/"],
    )
    connection = McpConnection.objects.create(
        user=user, client=oauth_client, resource=RESOURCE_MATTERS
    )
    access, _refresh, _expires = McpToken.issue(connection)
    return Client(HTTP_AUTHORIZATION=f"Bearer {access}")


def test_a_matters_token_reads_the_api_as_its_user(bearer, user, matter):
    body = bearer.get("/matters/api/").json()
    assert [m["id"] for m in body["matters"]] == [matter.id]
    assert body["user"] == {
        "name": user.get_full_name() or user.username,
        "email": user.email,
    }
    assert bearer.get(f"/matters/api/{matter.id}/").json()["matter"]["id"] == matter.id
    # Using it is recorded on the connection Settings > Claude lists.
    assert McpConnection.objects.get().last_used_at is not None


def test_a_bad_bearer_is_refused_even_with_a_good_api_token(user, matter):
    client = Client(
        HTTP_AUTHORIZATION="Bearer nope",
        HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(user).key,
    )
    response = client.get("/matters/api/")
    assert response.status_code == 401
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_a_matters_token_dies_with_its_user(bearer, user, matter):
    user.is_active = False
    user.save()
    assert bearer.get("/matters/api/").status_code == 401


def test_a_matters_token_is_limited_like_its_user(bearer, user, matter):
    user.perm_all_matters = False
    user.save()
    assert bearer.get("/matters/api/").json()["matters"] == []
    assert bearer.get(f"/matters/api/{matter.id}/").status_code == 404


def test_a_matters_token_opens_nothing_else(bearer, matter):
    # The other token APIs want X-Kosmos-Token; the MCP server its own
    # resource's token.
    assert bearer.get("/case/api/matters/").status_code == 401
    assert bearer.get("/search/api/?q=sample").status_code == 401
    assert bearer.post("/mcp", "{}", content_type="application/json").status_code == 401
    assert bearer.post("/matters/api/").status_code == 405
