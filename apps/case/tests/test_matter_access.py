"""A user limited to assigned matters (perm_all_matters off) gets nothing
from another matter's case workspace, whichever id the URL names it by.
Users who can see every matter are unaffected."""

import pytest
from django.test import Client

from apps.accounts.access import matter_ids_for_route
from apps.accounts.models import CustomUser
from apps.case.ai.models import Conversation, Message
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def restricted_user():
    user = CustomUser.objects.create(
        username="restricted", email="restricted@example.com", perm_all_matters=False
    )
    user.set_password("pw")
    user.save()
    return user


@pytest.fixture
def restricted_client(restricted_user):
    client = Client()
    client.login(username="restricted", password="pw")
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


@pytest.fixture
def conversation(matter, user):
    return Conversation.objects.create(matter=matter, user=user)


def _routes(matter, document, highlight, fact, conversation):
    """One route per way the case workspace names a matter's material."""
    return [
        f"/case/{matter.id}/documents/",
        f"/case/{matter.id}/facts/",
        f"/case/documents/{document.id}/download/",
        f"/case/documents/{document.id}/serve/",
        f"/case/documents/{document.id}/view/",
        f"/case/highlights/{highlight.id}/detail/",
        f"/case/facts/{fact.id}/edit/",
        f"/case/labels/apply/document/{document.id}/",
        f"/case/ai/conversations/{conversation.id}/view/",
    ]


def test_user_outside_the_matter_is_refused_everywhere(
    restricted_client, matter, document, highlight, fact, conversation
):
    for path in _routes(matter, document, highlight, fact, conversation):
        assert restricted_client.get(path).status_code == 403, path


def test_assigned_user_gets_through(
    restricted_client, restricted_user, matter, document, highlight, fact, conversation
):
    matter.members.add(restricted_user)

    for path in _routes(matter, document, highlight, fact, conversation):
        assert restricted_client.get(path).status_code != 403, path
    response = restricted_client.get(f"/case/documents/{document.id}/download/")
    assert response.status_code == 200


def test_user_with_all_matters_is_never_refused(
    client, matter, document, highlight, fact, conversation
):
    for path in _routes(matter, document, highlight, fact, conversation):
        assert client.get(path).status_code != 403, path


def test_writes_are_refused_too(restricted_client, document):
    response = restricted_client.post(f"/case/documents/{document.id}/delete/")

    assert response.status_code == 403
    assert type(document).objects.filter(pk=document.pk).exists()


def test_matter_switcher_lists_only_assigned_matters(
    restricted_client, restricted_user, matter, practice_area
):
    other = Matter.objects.create(
        name="Unassigned Matter Name", status="Open", practice_area=practice_area
    )
    matter.members.add(restricted_user)

    response = restricted_client.get(f"/case/{matter.id}/documents/")

    assert response.status_code == 200
    assert other.name not in response.content.decode()


def test_route_matter_is_found_from_each_kind_of_id(
    matter, document, highlight, fact, conversation, user
):
    message = Message.objects.create(
        conversation=conversation, role="user", content="Hello", user=user
    )
    for kwargs in (
        {"matter_id": matter.id},
        {"document_id": document.id},
        {"highlight_id": highlight.id},
        {"fact_id": fact.id},
        {"conv_id": conversation.id},
        {"message_id": message.id},
        {"object_type": "document", "object_id": document.id},
        {"object_type": "highlight", "object_id": highlight.id},
    ):
        assert matter_ids_for_route(kwargs) == {matter.id}, kwargs


def test_unknown_ids_and_matterless_rows_resolve_to_nothing(user):
    chat = Conversation.objects.create(matter=None, user=user)

    assert matter_ids_for_route({"document_id": 999999}) == set()
    assert matter_ids_for_route({"conv_id": chat.id}) == set()
    assert matter_ids_for_route({"tab": "documents"}) == set()


# --- Permission flags are enforced at the URL, not only in the navigation ---


@pytest.fixture
def limited_client(user):
    """Sees every matter, but with the research, financial and intakes
    permissions switched off."""
    user.perm_research = False
    user.perm_financial = False
    user.perm_intakes = False
    user.save()
    client = Client()
    client.login(username="testuser", password="testpass123")
    client.get("/dash/")
    return client


def test_case_law_is_refused_without_the_research_permission(limited_client, matter):
    assert limited_client.get(f"/case/{matter.id}/caselaws/").status_code == 403
    # The tab-switch route reaches the same page by another address.
    assert limited_client.get(f"/case/{matter.id}/tab/caselaws/").status_code == 403
    assert limited_client.get(f"/case/{matter.id}/tab/documents/").status_code == 200


def test_rates_and_ledger_are_refused_without_the_financial_permission(
    limited_client, matter
):
    assert limited_client.get(f"/matters/{matter.id}/rates").status_code == 403
    assert limited_client.get(f"/matters/{matter.id}/rates/add").status_code == 403
    assert limited_client.get(f"/matters/{matter.id}/ledger/").status_code == 403


def test_intake_email_settings_are_refused_without_the_intakes_permission(
    limited_client,
):
    assert limited_client.get("/settings/intake-emails/").status_code == 403


def test_the_same_pages_open_with_the_permissions_on(client, matter):
    assert client.get(f"/case/{matter.id}/caselaws/").status_code == 200
    assert client.get(f"/matters/{matter.id}/rates").status_code == 200
    assert client.get("/settings/intake-emails/").status_code == 200
