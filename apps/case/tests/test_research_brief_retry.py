"""A saved brief whose generation failed can be written again.

Any brief for the case used to block Save Brief, so the card showed
"Brief generation failed" with nothing to do but delete the brief."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.case.research import tasks as research_tasks
from apps.case.research.models import CaseBrief, ResearchQuery, ResearchResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def queued(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "django_q.tasks.async_task",
        lambda dotted, *args, **kwargs: calls.append((dotted.rsplit(".", 1)[1], args)),
    )
    return calls


@pytest.fixture
def result(matter, user):
    query = ResearchQuery.objects.create(
        matter=matter, query_text="fees on a mooted motion", created_by=user
    )
    ResearchQuery.objects.filter(pk=query.pk).update(status="complete")
    return ResearchResult.objects.create(
        query=query, position=1, case_name="Birg v. Emory", cluster_id=9
    )


@pytest.fixture
def failed_brief(matter, user):
    brief = CaseBrief.objects.create(
        matter=matter,
        cluster_id=9,
        status="error",
        brief="Could not retrieve opinion text.",
        created_by=user,
    )
    # Long untouched: a retry that forgot the heartbeat would be reaped
    # as failed on the next poll.
    stale = timezone.now() - timedelta(
        minutes=research_tasks.RESEARCH_STALE_MINUTES + 1
    )
    CaseBrief.objects.filter(pk=brief.pk).update(updated_at=stale)
    return brief


def _retry_url(brief):
    return reverse("case:research-retry-brief", args=[brief.id])


def test_the_card_offers_retry_for_a_failed_brief(client, result, failed_brief):
    html = client.get(
        reverse("case:research-result-status", args=[result.id])
    ).content.decode()

    assert "Brief generation failed" in html
    assert _retry_url(failed_brief) in html


def test_retry_queues_the_same_brief_again(client, result, failed_brief, queued):
    html = client.post(_retry_url(failed_brief)).content.decode()

    assert queued == [("_generate_brief", (failed_brief.id,))]
    failed_brief.refresh_from_db()
    assert failed_brief.status == "pending"
    assert failed_brief.brief == ""
    assert CaseBrief.objects.count() == 1
    assert "Generating Brief..." in html
    assert reverse("case:research-brief-status", args=[failed_brief.id]) in html

    # The poll keeps waiting on it rather than failing it as stale.
    poll = client.get(
        reverse("case:research-brief-status", args=[failed_brief.id])
    ).content.decode()
    assert "Generating Brief..." in poll


def test_save_brief_on_a_failed_brief_retries_it(client, result, failed_brief, queued):
    html = client.post(
        reverse("case:research-save-brief", args=[result.id])
    ).content.decode()

    assert queued == [("_generate_brief", (failed_brief.id,))]
    failed_brief.refresh_from_db()
    assert failed_brief.status == "pending"
    assert failed_brief.result == result
    assert CaseBrief.objects.count() == 1
    assert "Generating Brief..." in html


def test_retry_refuses_a_brief_that_did_not_fail(client, matter, user, queued):
    brief = CaseBrief.objects.create(
        matter=matter,
        cluster_id=9,
        status="complete",
        brief="## Facts",
        created_by=user,
    )

    response = client.post(_retry_url(brief))

    assert response.status_code == 404
    assert queued == []


def test_retry_refuses_a_plain_link(client, failed_brief, queued):
    response = client.get(_retry_url(failed_brief))

    assert response.status_code == 405
    assert queued == []


def test_retry_refuses_a_colleagues_brief(client, matter, failed_brief, queued):
    from apps.accounts.models import CustomUser

    other = CustomUser.objects.create(username="other", user_rate=100)
    CaseBrief.objects.filter(pk=failed_brief.pk).update(created_by=other)

    response = client.post(_retry_url(failed_brief))

    assert response.status_code == 404
    assert queued == []
