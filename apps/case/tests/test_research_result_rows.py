"""A result card on the Research tab, each time it is drawn.

Brief case marks the card as working before the task is queued, so the
card that comes back already shows the job and polls for it. Every
re-render of a card (the poll, a bookmark, a saved brief) carries the same
saved state as the list. A job whose task was lost ends with a message
instead of spinning."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.case.models import CaseLaw
from apps.case.research import (
    tasks as research_tasks,
    views as research_views,
)
from apps.case.research.models import CaseBrief, ResearchQuery, ResearchResult

pytestmark = pytest.mark.django_db


@pytest.fixture
def queued(monkeypatch):
    """Record what is queued without running it."""
    calls = []
    monkeypatch.setattr(
        "django_q.tasks.async_task",
        lambda dotted, *args, **kwargs: calls.append((dotted.rsplit(".", 1)[1], args)),
    )
    return calls


@pytest.fixture
def query(matter, user):
    query = ResearchQuery.objects.create(
        matter=matter, query_text="fees on a mooted motion", created_by=user
    )
    ResearchQuery.objects.filter(pk=query.pk).update(status="complete")
    query.refresh_from_db()
    return query


@pytest.fixture
def result(query):
    return ResearchResult.objects.create(
        query=query,
        position=1,
        case_name="Birg v. Emory",
        court="Court of Appeals of Georgia",
        cluster_id=9,
        relevance="none",
    )


def _long_ago():
    return timezone.now() - timedelta(minutes=research_tasks.RESEARCH_STALE_MINUTES + 1)


def _status_url(result):
    return reverse("case:research-result-status", args=[result.id])


class TestBriefCase:
    def test_the_card_shows_the_job_as_soon_as_it_is_clicked(
        self, client, result, queued
    ):
        url = reverse("case:research-summarize-result", args=[result.id])

        html = client.post(url).content.decode()

        result.refresh_from_db()
        assert result.relevance == "pending"
        assert queued == [("_summarize_result", (result.id,))]
        assert _status_url(result) in html
        assert "Queued for briefing" in html

    def test_a_second_click_does_not_queue_a_second_job(self, client, result, queued):
        url = reverse("case:research-summarize-result", args=[result.id])

        client.post(url)
        client.post(url)

        assert len(queued) == 1

    def test_a_lost_job_ends_with_a_message_and_the_button_back(
        self, client, result, queued
    ):
        ResearchResult.objects.filter(pk=result.pk).update(
            relevance="pending", status_message="Briefing...", updated_at=_long_ago()
        )

        html = client.get(_status_url(result)).content.decode()

        result.refresh_from_db()
        assert result.relevance == "error"
        assert research_tasks.BRIEF_INTERRUPTED in html
        assert _status_url(result) not in html
        assert reverse("case:research-summarize-result", args=[result.id]) in html

    def test_a_job_still_inside_the_window_keeps_polling(self, client, result):
        research_tasks._stamp(ResearchResult, result.pk, relevance="pending")

        html = client.get(_status_url(result)).content.decode()

        result.refresh_from_db()
        assert result.relevance == "pending"
        assert _status_url(result) in html

    def test_a_running_pipeline_keeps_its_own_pending_rows(self, client, query, result):
        ResearchQuery.objects.filter(pk=query.pk).update(status="processing")
        ResearchResult.objects.filter(pk=result.pk).update(
            relevance="pending", updated_at=_long_ago()
        )

        client.get(_status_url(result))

        result.refresh_from_db()
        assert result.relevance == "pending"

    def test_a_failed_brief_says_why(self, client, result):
        ResearchResult.objects.filter(pk=result.pk).update(
            relevance="error", status_message="Could not fetch opinion text"
        )

        html = client.get(_status_url(result)).content.decode()

        assert "Could not fetch opinion text" in html


class TestSavedStateOnEveryRender:
    def test_the_poll_keeps_the_bookmark_and_the_saved_brief(
        self, client, matter, user, result
    ):
        CaseLaw.objects.create(
            matter=matter, case_name="Birg v. Emory", citation="", cluster_id=9
        )
        brief = CaseBrief.objects.create(
            matter=matter,
            cluster_id=9,
            brief="## Facts",
            status="complete",
            created_by=user,
        )

        html = client.get(_status_url(result)).content.decode()

        assert 'title="Bookmarked"' in html
        assert reverse("case:research-save-caselaw", args=[result.id]) not in html
        assert reverse("case:research-brief-detail", args=[brief.id]) in html
        assert reverse("case:research-save-brief", args=[result.id]) not in html

    def test_a_card_with_nothing_saved_offers_both(self, client, result):
        html = client.get(_status_url(result)).content.decode()

        assert 'title="Bookmark Case"' in html
        assert reverse("case:research-save-caselaw", args=[result.id]) in html
        assert reverse("case:research-save-brief", args=[result.id]) in html

    def test_saving_a_brief_shows_it_being_written(self, client, result, monkeypatch):
        monkeypatch.setattr(research_views, "generate_brief", lambda brief_id: None)

        html = client.post(
            reverse("case:research-save-brief", args=[result.id])
        ).content.decode()

        brief = CaseBrief.objects.get(cluster_id=9)
        assert reverse("case:research-brief-status", args=[brief.id]) in html
        assert "Generating Brief..." in html

    def test_brief_case_keeps_the_bookmark(self, client, matter, result, queued):
        CaseLaw.objects.create(
            matter=matter, case_name="Birg v. Emory", citation="", cluster_id=9
        )

        html = client.post(
            reverse("case:research-summarize-result", args=[result.id])
        ).content.decode()

        assert 'title="Bookmarked"' in html


class TestSavedBrief:
    def test_a_lost_brief_ends_as_failed(self, client, matter, user):
        brief = CaseBrief.objects.create(
            matter=matter, cluster_id=9, status="generating", created_by=user
        )
        CaseBrief.objects.filter(pk=brief.pk).update(updated_at=_long_ago())
        url = reverse("case:research-brief-status", args=[brief.id])

        html = client.get(url).content.decode()

        brief.refresh_from_db()
        assert brief.status == "error"
        assert "Brief generation failed" in html
        assert "hx-get" not in html

    def test_a_brief_being_written_keeps_polling(self, client, matter, user):
        brief = CaseBrief.objects.create(
            matter=matter, cluster_id=9, status="generating", created_by=user
        )
        url = reverse("case:research-brief-status", args=[brief.id])

        html = client.get(url).content.decode()

        assert url in html
