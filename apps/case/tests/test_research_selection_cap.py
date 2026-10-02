"""The case selection screen briefs at most BRIEF_MAX cases at a time.

The selected cases are briefed inside one task with a ten-minute limit.
There was no upper limit on the selection, so ticking everything could
run the task out of time and lose the run. The server refuses a larger
selection with a message (keeping the ticks), and the screen's counter
turns Run briefs off above the limit."""

import pytest
from django.urls import reverse

from apps.case.research import views as research_views
from apps.case.research.models import ResearchQuery, ResearchResult
from apps.case.research.tasks import BRIEF_MAX

pytestmark = pytest.mark.django_db


@pytest.fixture
def query(matter, user):
    query = ResearchQuery.objects.create(
        matter=matter, query_text="fees on a mooted motion", created_by=user
    )
    ResearchQuery.objects.filter(pk=query.pk).update(
        status="selecting", structured_query="fees"
    )
    query.refresh_from_db()
    return query


@pytest.fixture
def candidates(query):
    return [
        ResearchResult.objects.create(
            query=query,
            position=position,
            case_name=f"Case {position}",
            cluster_id=100 + position,
            relevance="pending",
            recommended=position <= 2,
        )
        for position in range(1, BRIEF_MAX + 5)
    ]


@pytest.fixture
def started(monkeypatch):
    calls = []
    monkeypatch.setattr(research_views, "process_brief_phase", calls.append)
    return calls


def _select(client, matter, query, results):
    return client.post(
        reverse("case:research-select", args=[matter.id, query.id]),
        {f"case_{r.id}": "on" for r in results},
    )


def test_more_than_the_limit_is_refused_with_a_message(
    client, matter, query, candidates, started
):
    chosen = candidates[: BRIEF_MAX + 1]

    response = _select(client, matter, query, chosen)

    query.refresh_from_db()
    assert started == []
    assert query.status == "selecting"
    assert not query.results.exclude(relevance="pending").exists()
    html = response.content.decode()
    assert f"Select at most {BRIEF_MAX} cases" in html
    assert f"{BRIEF_MAX + 1} are selected" in html


def test_the_refused_selection_comes_back_ticked_as_it_was_sent(
    client, matter, query, candidates, started
):
    chosen = candidates[2 : BRIEF_MAX + 3]  # not the two recommended ones

    html = _select(client, matter, query, chosen).content.decode()

    def ticked(result):
        box = html.split(f'id="case-{result.id}"')[1].split(">")[0]
        return "checked" in box

    assert all(ticked(r) for r in chosen)
    assert not ticked(candidates[0])
    assert not ticked(candidates[-1])


def test_exactly_the_limit_runs(client, matter, query, candidates, started):
    chosen = candidates[:BRIEF_MAX]

    response = _select(client, matter, query, chosen)

    query.refresh_from_db()
    assert response.status_code == 200
    assert started == [query.id]
    assert query.status == "processing"
    assert query.results.filter(relevance="pending").count() == BRIEF_MAX


def test_the_screen_carries_the_limit_for_its_counter(
    client, matter, query, candidates
):
    url = reverse("case:research-results", args=[matter.id, query.id])

    html = client.get(url).content.decode()

    form = html.split('id="researchSelForm"')[1].split(">")[0]
    assert f'data-max="{BRIEF_MAX}"' in form
    assert f"({BRIEF_MAX} at most)" in html
    # The counter's rule: off with nothing ticked, and off above the limit.
    assert "count === 0 || count > max" in html
