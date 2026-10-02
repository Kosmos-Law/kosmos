"""The Validate sub-tab: checking how later opinions treat a case.

Validating by a typed citation works inside the tab like the Validate
button on a card. Validating the same case twice does not list its citing
opinions twice. An assessment that cannot be made ends with a message
instead of a spinner that never stops."""

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.case.courtlistener import CaseLookupResult, OpinionResult
from apps.case.research import (
    tasks as research_tasks,
    views as research_views,
)
from apps.case.research.models import (
    CitationVerification,
    ResearchQuery,
    ResearchResult,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def result(matter, user):
    query = ResearchQuery.objects.create(
        matter=matter, query_text="fees on a mooted motion", created_by=user
    )
    ResearchQuery.objects.filter(pk=query.pk).update(status="complete")
    return ResearchResult.objects.create(
        query=query,
        position=1,
        case_name="Birg v. Emory",
        citation="300 Ga. App. 1",
        cluster_id=9,
        relevance="high",
    )


@pytest.fixture
def queued(monkeypatch):
    """Record what is queued without running it."""
    calls = []
    monkeypatch.setattr(
        "django_q.tasks.async_task",
        lambda dotted, *args, **kwargs: calls.append((dotted.rsplit(".", 1)[1], args)),
    )
    return calls


def _verification(result, position=1, **fields):
    return CitationVerification.objects.create(
        result=result,
        position=position,
        case_name=f"Citing case {position}",
        cluster_id=500 + position,
        depth=3,
        **fields,
    )


def _long_ago():
    return timezone.now() - timedelta(minutes=research_tasks.RESEARCH_STALE_MINUTES + 1)


# --- Validate by a typed citation ---


class TestLookupInTheTab:
    def test_the_form_posts_inside_the_tab(self, client, matter):
        url = reverse("case:research-review-tab", args=[matter.id])

        html = client.get(url).content.decode()

        form = html.split('class="research-review-lookup"')[0].rsplit("<form", 1)[1]
        assert reverse("case:research-review-lookup", args=[matter.id]) in form
        assert "hx-post" in form
        assert 'hx-target="#research"' in form
        assert "method=" not in form

    def test_a_found_citation_renders_the_tab_with_the_live_status(
        self, client, matter, monkeypatch
    ):
        monkeypatch.setattr(
            research_views,
            "lookup_citation",
            lambda text: CaseLookupResult(
                found=True,
                case_name="Roe v. Wade",
                citation="410 U.S. 113",
                court="Supreme Court",
                date_filed=date(1973, 1, 22),
                cluster_id=77,
            ),
        )
        monkeypatch.setattr(research_views, "fetch_cluster", lambda cluster_id: {})
        started = []
        monkeypatch.setattr(research_views, "review_result", started.append)

        response = client.post(
            reverse("case:research-review-lookup", args=[matter.id]),
            {"citation": "410 U.S. 113"},
        )

        result = ResearchResult.objects.get(cluster_id=77)
        assert started == [result.id]
        assert response.status_code == 200
        assert "case/research/list.html" in [t.name for t in response.templates]
        html = response.content.decode()
        assert "research-internal-nav" in html
        assert "Roe v. Wade" in html
        assert reverse("case:research-review-status", args=[result.id]) in html

    def test_a_citation_that_is_not_found_says_so_in_the_tab(
        self, client, matter, monkeypatch
    ):
        monkeypatch.setattr(
            research_views,
            "lookup_citation",
            lambda text: CaseLookupResult(found=False, error="No results found"),
        )

        response = client.post(
            reverse("case:research-review-lookup", args=[matter.id]),
            {"citation": "1 Nowhere 1"},
        )

        html = response.content.decode()
        assert "No results found" in html
        assert "research-internal-nav" in html


# --- Validating the same case twice ---


@pytest.fixture
def citing_cases(monkeypatch):
    """A CourtListener with a settable list of opinions citing the case."""
    state = {"citing": [601, 602], "assessments": 0}

    def fake_gemini(system_prompt, messages, **kwargs):
        # The case's own summary is asked for too; only assessments count.
        if "citing opinion" in messages[0]["content"]:
            state["assessments"] += 1
        return '{"treatment": "positive", "summary": "Follows it."}', None, None

    monkeypatch.setattr(
        research_tasks,
        "fetch_cluster",
        lambda cluster_id: {"sub_opinions": [f"https://api/opinions/{cluster_id}/"]},
    )
    monkeypatch.setattr(
        research_tasks,
        "fetch_opinion",
        lambda opinion_id: OpinionResult(found=True, plain_text="Opinion text."),
    )
    monkeypatch.setattr(
        research_tasks,
        "get_forward_citations",
        lambda opinion_id, limit=20: [
            {"citing_opinion_id": oid, "depth": 3} for oid in state["citing"]
        ],
    )
    monkeypatch.setattr(
        research_tasks,
        "_get_opinion_metadata",
        lambda opinion_id: {
            "case_name": f"Citing {opinion_id}",
            "cluster_id": opinion_id,
        },
    )
    monkeypatch.setattr(research_tasks, "send_to_gemini", fake_gemini)
    return state


class TestValidatingTwice:
    def test_the_citing_opinions_are_listed_once(self, result, citing_cases):
        research_tasks._review_result(result.id)
        research_tasks._review_result(result.id)

        rows = CitationVerification.objects.filter(result=result)
        assert sorted(rows.values_list("cluster_id", flat=True)) == [601, 602]
        assert sorted(rows.values_list("position", flat=True)) == [1, 2]

    def test_assessments_already_made_are_kept_not_redone(self, result, citing_cases):
        research_tasks._review_result(result.id)
        assert citing_cases["assessments"] == 2

        research_tasks._review_result(result.id)

        assert citing_cases["assessments"] == 2
        assert not CitationVerification.objects.filter(result=result, summary="")

    def test_a_new_citing_opinion_is_added_after_the_ones_listed(
        self, result, citing_cases
    ):
        research_tasks._review_result(result.id)
        citing_cases["citing"] = [603, 601, 602]

        research_tasks._review_result(result.id)

        rows = CitationVerification.objects.filter(result=result).order_by("position")
        assert list(rows.values_list("cluster_id", flat=True)) == [601, 602, 603]

    def test_clicking_validate_while_one_runs_does_not_start_another(
        self, client, result, queued
    ):
        url = reverse("case:research-review", args=[result.id])

        client.post(url)
        html = client.post(url).content.decode()

        assert queued == [("_review_result", (result.id,))]
        assert reverse("case:research-review-status", args=[result.id]) in html

    def test_a_lost_validation_ends_as_failed(self, client, result):
        ResearchResult.objects.filter(pk=result.pk).update(
            verify_status="verifying", updated_at=_long_ago()
        )
        url = reverse("case:research-review-status", args=[result.id])

        html = client.get(url).content.decode()

        result.refresh_from_db()
        assert result.verify_status == "error"
        assert "Validation failed" in html
        assert "hx-get" not in html


# --- One citing opinion's assessment ---


class TestAssessment:
    def _status(self, client, verification):
        url = reverse("case:research-citation-status", args=[verification.id])
        return url, client.get(url).content.decode()

    def test_an_opinion_that_cannot_be_fetched_ends_with_a_message(
        self, client, result, monkeypatch
    ):
        verification = _verification(result)
        monkeypatch.setattr(research_tasks, "fetch_cluster", lambda cluster_id: None)

        research_tasks._assess_single_citation(verification.id)

        verification.refresh_from_db()
        assert verification.summary == research_tasks.ASSESS_FETCH_FAILED
        assert verification.treatment == ""
        url, html = self._status(client, verification)
        assert research_tasks.ASSESS_FETCH_FAILED in html
        assert url not in html
        assert reverse("case:research-assess-citation", args=[verification.id]) in html

    def test_a_model_failure_ends_with_a_message_and_no_verdict(
        self, client, result, citing_cases, monkeypatch
    ):
        verification = _verification(result)

        def boom(*args, **kwargs):
            raise RuntimeError("model unavailable")

        monkeypatch.setattr(research_tasks, "send_to_gemini", boom)

        research_tasks._assess_single_citation(verification.id)

        verification.refresh_from_db()
        assert verification.summary == research_tasks.ASSESS_FAILED
        assert verification.treatment == ""
        _, html = self._status(client, verification)
        assert "Neutral" not in html

    def test_a_good_assessment_shows_its_verdict(self, client, result, citing_cases):
        verification = _verification(result)

        research_tasks._assess_single_citation(verification.id)

        verification.refresh_from_db()
        assert verification.treatment == "positive"
        url, html = self._status(client, verification)
        assert "Follows it." in html
        assert "Positive" in html
        assert url not in html

    def test_a_lost_assessment_stops_polling_and_says_so(self, client, result):
        verification = _verification(result)
        CitationVerification.objects.filter(pk=verification.pk).update(
            updated_at=_long_ago()
        )

        url, html = self._status(client, verification)

        assert research_tasks.ASSESS_INTERRUPTED in html
        assert url not in html
        assert reverse("case:research-assess-citation", args=[verification.id]) in html

    def test_assessing_polls_until_there_is_an_outcome(self, client, result, queued):
        verification = _verification(result)

        html = client.post(
            reverse("case:research-assess-citation", args=[verification.id])
        ).content.decode()

        assert queued == [("_assess_single_citation", (verification.id,))]
        assert reverse("case:research-citation-status", args=[verification.id]) in html

    def test_assessing_again_clears_the_failed_attempt(self, client, result, queued):
        verification = _verification(
            result, summary=research_tasks.ASSESS_FETCH_FAILED, treatment=""
        )

        html = client.post(
            reverse("case:research-assess-citation", args=[verification.id])
        ).content.decode()

        verification.refresh_from_db()
        assert verification.summary == ""
        assert research_tasks.ASSESS_FETCH_FAILED not in html
        assert reverse("case:research-citation-status", args=[verification.id]) in html
