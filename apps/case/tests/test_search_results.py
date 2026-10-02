"""Case Search over keyword matches: a highlight on a court opinion has no
document and must not break the page, and the importance filter means "at
least", as it is labelled."""

from types import SimpleNamespace

import pytest
from django.urls import reverse

from apps.case.models import CaseLaw, Document, Highlight

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_semantic_pass(monkeypatch):
    monkeypatch.setattr("apps.case.search.views.semantic_entries", lambda *a, **k: [])


@pytest.fixture
def keyword_hits(monkeypatch):
    """Make the keyword search return exactly these objects."""

    def install(*objects):
        hits = [SimpleNamespace(object=obj, watson_rank=1.0) for obj in objects]
        monkeypatch.setattr("apps.case.search.views.watson.search", lambda query: hits)

    return install


def _search(client, matter, **filters):
    session = client.session
    session[f"search_filter_{matter.id}"] = {"query": "negligence", **filters}
    session.save()
    return client.get(reverse("case:search-results", args=[matter.id]))


def test_keyword_match_on_a_case_law_highlight_does_not_break_search(
    client, user, matter, highlight, keyword_hits
):
    case_law = CaseLaw.objects.create(
        matter=matter, citation="1 U.S. 1", case_name="A v. B", court="Supreme Court"
    )
    opinion_highlight = Highlight.objects.create(
        caselaw=case_law,
        slug="Opinion passage",
        text="negligence per se",
        page_number=1,
        coordinates={"rects": []},
        color="yellow",
        created_by=user,
    )
    keyword_hits(opinion_highlight, highlight)

    response = _search(client, matter)

    assert response.status_code == 200
    results = response.context["results"]
    assert [r["object"] for r in results] == [highlight]


def _document(matter, user, name, importance):
    doc = Document(
        matter=matter,
        name=name,
        category="Evidence",
        created_by=user,
        importance=importance,
        ocr_status="not_applicable",
    )
    doc.save()
    return doc


def test_importance_filter_keeps_results_at_least_that_important(
    client, user, matter, keyword_hits
):
    low = _document(matter, user, "Low", 2)
    normal = _document(matter, user, "Normal", 4)
    high = _document(matter, user, "High", 6)
    keyword_hits(low, normal, high)

    response = _search(client, matter, importance="4")

    names = sorted(r["object"].name for r in response.context["results"])
    assert names == ["High", "Normal"]
