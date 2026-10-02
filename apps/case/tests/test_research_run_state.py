"""What the Research tab shows about a run: one in progress, one that
failed, and its cards while it is still working."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.case.research import tasks as research_tasks
from apps.case.research.models import ResearchQuery, ResearchResult

pytestmark = pytest.mark.django_db


def _query(matter, user, **fields):
    query = ResearchQuery.objects.create(
        matter=matter, query_text="fees on a mooted motion", created_by=user
    )
    if fields:
        ResearchQuery.objects.filter(pk=query.pk).update(**fields)
        query.refresh_from_db()
    return query


def _result(query, position, **fields):
    return ResearchResult.objects.create(
        query=query,
        position=position,
        case_name=f"Case {position}",
        cluster_id=100 + position,
        **fields,
    )


# --- Opening the tab shows the run in progress, whichever way it is opened ---


@pytest.mark.parametrize(
    "path",
    [
        "/case/{matter}/research/",
        "/case/{matter}/tab/research/",
        "/case/{matter}/research/list/",
        "/case/{matter}/research/search-tab/",
    ],
    ids=["full page", "tab switch", "list refresh", "Search sub-tab"],
)
def test_every_way_in_shows_the_run_in_progress(client, matter, user, path):
    query = _query(matter, user, status="refining")

    html = client.get(path.format(matter=matter.id)).content.decode()

    assert "Refining query..." in html
    assert reverse("case:research-query-status", args=[query.id]) in html


def test_a_colleagues_run_is_not_shown(client, matter, user):
    from apps.accounts.models import CustomUser

    colleague = CustomUser.objects.create(username="colleague", email="c@example.com")
    _query(matter, colleague, status="refining")

    html = client.get(f"/case/{matter.id}/research/").content.decode()

    assert "Refining query..." not in html


# --- A run that fails says so, and stops polling ---


def test_a_failed_refinement_shows_its_message(client, matter, user):
    query = _query(
        matter,
        user,
        status="error",
        error_message="An error occurred while refining the query.",
    )
    url = reverse("case:research-query-status", args=[query.id])

    html = client.get(url).content.decode()

    assert "An error occurred while refining the query." in html
    assert "hx-get" not in html


def test_a_lost_refinement_ends_instead_of_polling_forever(client, matter, user):
    stale = timezone.now() - timedelta(
        minutes=research_tasks.RESEARCH_STALE_MINUTES + 1
    )
    query = _query(matter, user, status="refining", updated_at=stale)
    url = reverse("case:research-query-status", args=[query.id])

    html = client.get(url).content.decode()

    query.refresh_from_db()
    assert query.status == "error"
    assert "Interrupted before it finished" in html
    assert "hx-get" not in html


def test_a_failed_answer_completes_the_run_with_a_message(
    client, matter, user, monkeypatch
):
    query = _query(matter, user, status="synthesizing", structured_query="fees")
    _result(query, 1, relevance="high", brief="CASE: Case 1")

    def boom(*args, **kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(research_tasks, "send_to_gemini", boom)

    research_tasks._generate_final_answer(query.id)

    query.refresh_from_db()
    assert query.status == "complete"
    assert query.final_summary == ""
    assert query.error_message == research_tasks.ANSWER_FAILED

    url = reverse("case:research-results", args=[matter.id, query.id])
    html = client.get(url).content.decode()
    assert research_tasks.ANSWER_FAILED in html
    assert "Case 1" in html


def test_a_successful_answer_shows_no_error(client, matter, user, monkeypatch):
    query = _query(matter, user, status="synthesizing", structured_query="fees")
    _result(query, 1, relevance="high", brief="CASE: Case 1")
    monkeypatch.setattr(
        research_tasks, "send_to_gemini", lambda *a, **k: ("The answer.", None, None)
    )

    research_tasks._generate_final_answer(query.id)

    query.refresh_from_db()
    assert query.final_summary == "The answer."
    assert query.error_message == ""


# --- While a run is working, every card can be reached ---


@pytest.mark.parametrize("status", ["processing", "enriching", "synthesizing"])
def test_a_working_run_has_page_controls(client, matter, user, status):
    query = _query(matter, user, status=status, structured_query="fees")
    for position in range(1, 8):
        _result(query, position, relevance="high")
    url = reverse("case:research-results", args=[matter.id, query.id])

    html = client.get(url).content.decode()

    assert "Page 1 of 2" in html
    assert "/change-page/" in html
    assert "Case 5" in html and "Case 6" not in html

    client.get(
        reverse(
            "management:change-page",
            kwargs={
                "session_key": f"research_results_{query.id}",
                "trigger_key": "researchResultsChanged",
                "page": 2,
            },
        )
    )
    html = client.get(url).content.decode()
    assert "Page 2 of 2" in html
    assert "Case 6" in html and "Case 7" in html


def test_a_citation_lookup_is_not_shown_as_a_search(client, matter, user):
    """Validating a typed citation stores its case under a placeholder
    query; the Search sub-tab shows the last real search instead."""
    real = _query(matter, user, status="complete", structured_query="fees")
    _query(matter, user, status="complete")

    response = client.get(f"/case/{matter.id}/research/search-tab/")

    assert response.context["active_query"] == real
