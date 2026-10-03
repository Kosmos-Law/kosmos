"""Case briefs are per user.

A brief is written against its author's own research question, and the
Case Briefs list, the brief page and its delete all look only at the
signed-in user's briefs. The results list has to agree: a colleague's
brief of the same case is not offered as "View Brief" (it would answer
404), and does not stop the user saving a brief of their own."""

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.case.research import views as research_views
from apps.case.research.models import CaseBrief, ResearchQuery, ResearchResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def colleague():
    return CustomUser.objects.create(username="colleague", email="c@example.com")


@pytest.fixture
def result(matter, user):
    query = ResearchQuery.objects.create(
        matter=matter, query_text="fees on a mooted motion", created_by=user
    )
    query.status = "complete"
    query.save()
    return ResearchResult.objects.create(
        query=query,
        position=1,
        case_name="Birg v. Emory",
        court="Court of Appeals of Georgia",
        cluster_id=9,
        relevance="high",
    )


def _brief(matter, author, **extra):
    return CaseBrief.objects.create(
        matter=matter,
        case_name="Birg v. Emory",
        cluster_id=9,
        brief="## Facts\nSome facts.",
        status="complete",
        created_by=author,
        **extra,
    )


def _results_html(client, matter, result):
    url = reverse("case:research-results", args=[matter.id, result.query_id])
    response = client.get(url)
    assert response.status_code == 200
    return response.content.decode()


def test_a_colleagues_brief_is_not_offered_as_view_brief(
    client, matter, result, colleague
):
    theirs = _brief(matter, colleague)

    html = _results_html(client, matter, result)

    assert reverse("case:research-brief-detail", args=[theirs.id]) not in html
    assert reverse("case:research-save-brief", args=[result.id]) in html
    assert (
        client.get(reverse("case:research-brief-detail", args=[theirs.id])).status_code
        == 404
    )


def test_the_users_own_brief_is_offered_and_opens(client, matter, result, user):
    mine = _brief(matter, user)

    html = _results_html(client, matter, result)

    detail = reverse("case:research-brief-detail", args=[mine.id])
    assert detail in html
    assert client.get(detail).status_code == 200


def test_a_colleagues_brief_does_not_block_saving_ones_own(
    client, matter, result, user, colleague, monkeypatch
):
    theirs = _brief(matter, colleague)
    queued = []
    monkeypatch.setattr(research_views, "generate_brief", queued.append)

    response = client.post(reverse("case:research-save-brief", args=[result.id]))

    assert response.status_code == 200
    mine = CaseBrief.objects.get(matter=matter, cluster_id=9, created_by=user)
    assert mine.id != theirs.id
    assert queued == [mine.id]
    html = response.content.decode()
    assert reverse("case:research-brief-status", args=[mine.id]) in html
    assert reverse("case:research-brief-detail", args=[theirs.id]) not in html


def test_saving_twice_returns_the_users_existing_brief(
    client, matter, result, user, monkeypatch
):
    mine = _brief(matter, user)
    monkeypatch.setattr(research_views, "generate_brief", lambda brief_id: None)

    response = client.post(reverse("case:research-save-brief", args=[result.id]))

    assert CaseBrief.objects.filter(matter=matter, cluster_id=9).count() == 1
    assert (
        reverse("case:research-brief-detail", args=[mine.id])
        in response.content.decode()
    )
