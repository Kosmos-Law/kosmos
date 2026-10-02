"""Column sorts on the Highlights, Facts and Witnesses lists.

Date on Highlights means the date the Date column shows (the document's,
or the saved case's filing date), not when the highlight was made. The
importance column starts highest first and a second click reverses it."""

from datetime import date

import pytest

from apps.case.models import CaseLaw, Document, Highlight

pytestmark = pytest.mark.django_db


def _highlight_on(matter, user, doc_date, slug):
    document = Document.objects.create(
        matter=matter,
        name=f"Document for {slug}",
        category="Evidence",
        created_by=user,
        date=doc_date,
        ocr_status="not_applicable",
    )
    return Highlight.objects.create(
        document=document, slug=slug, text=slug, page_number=1, created_by=user
    )


def _listed(client, matter):
    response = client.get(f"/case/{matter.id}/highlights/list/")
    return [h.slug for h in response.context["highlights"]]


def test_date_sorts_highlights_by_the_documents_date(client, matter, user):
    # Created newest-document-first, so creation order is the reverse of
    # document-date order and the two sorts cannot be confused.
    _highlight_on(matter, user, date(2024, 3, 1), "March")
    _highlight_on(matter, user, date(2024, 1, 1), "January")
    _highlight_on(matter, user, None, "Undated")
    case_law = CaseLaw.objects.create(
        matter=matter,
        case_name="Roe v. Wade",
        citation="410 U.S. 113",
        date_filed=date(2024, 2, 1),
    )
    Highlight.objects.create(
        caselaw=case_law, slug="February case", text="x", created_by=user
    )

    client.get(f"/case/{matter.id}/highlights/filter/sort/date/")
    assert _listed(client, matter) == ["January", "February case", "March", "Undated"]

    client.get(f"/case/{matter.id}/highlights/filter/sort/date/")
    assert _listed(client, matter) == ["March", "February case", "January", "Undated"]


@pytest.mark.parametrize(
    "tab, sort_path",
    [
        ("highlights", "highlights/filter/sort"),
        ("facts", "facts/sort"),
        ("witnesses", "witnesses/sort"),
    ],
)
def test_the_importance_sort_reverses_on_a_second_click(client, matter, tab, sort_path):
    """The column header always sends "-importance" (highest first)."""
    key = f"{tab}_filter_{matter.id}"
    url = f"/case/{matter.id}/{sort_path}/-importance/"

    client.get(url)
    assert client.session[key]["order_by"] == "-importance"
    client.get(url)
    assert client.session[key]["order_by"] == "importance"
    client.get(url)
    assert client.session[key]["order_by"] == "-importance"


def test_importance_order_is_applied_to_highlights(client, matter, user):
    low = _highlight_on(matter, user, None, "Low")
    high = _highlight_on(matter, user, None, "High")
    Highlight.objects.filter(pk=low.pk).update(importance=2)
    Highlight.objects.filter(pk=high.pk).update(importance=6)
    url = f"/case/{matter.id}/highlights/filter/sort/-importance/"

    client.get(url)
    assert _listed(client, matter) == ["High", "Low"]
    client.get(url)
    assert _listed(client, matter) == ["Low", "High"]
