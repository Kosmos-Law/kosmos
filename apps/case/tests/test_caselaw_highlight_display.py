"""A highlight on a saved case shows the case's date and a named
importance level, as a document highlight does.

The highlight card read only document.date (so a case-law highlight said
"No date"), and the case-law viewer printed importance as a bare number.
"""

from datetime import date

import pytest
from django.urls import reverse

from apps.case.models import CaseLaw, Highlight

pytestmark = pytest.mark.django_db


@pytest.fixture
def case_law(matter, user):
    return CaseLaw.objects.create(
        matter=matter,
        case_name="Roe v. Wade",
        citation="410 U.S. 113",
        date_filed=date(1973, 1, 22),
        text="The opinion of the court. " * 40,
        created_by=user,
    )


@pytest.fixture
def caselaw_highlight(case_law, user):
    return Highlight.objects.create(
        caselaw=case_law,
        slug="Holding",
        text="The opinion of the court.",
        char_offset=0,
        importance=6,
        created_by=user,
    )


def test_card_shows_the_date_the_case_was_filed(
    client, caselaw_highlight, global_label
):
    html = client.post(
        reverse("case:add-label-to", args=["highlight", caselaw_highlight.id]),
        {"label_id": global_label.id},
    ).content.decode()

    assert "highlight-card" in html
    assert "January 22, 1973" in html
    assert "No date" not in html


def test_viewer_names_the_importance_level(client, case_law, caselaw_highlight):
    html = client.get(
        reverse("case:caselaw-viewer", args=[case_law.id])
    ).content.decode()

    assert '<i class="icon-flag"></i> Higher' in html
    assert '<i class="icon-flag"></i> 6' not in html
    assert '"6": "Higher"' in html


def test_importance_name_follows_the_shared_scale(caselaw_highlight):
    assert caselaw_highlight.importance_name == "Higher"
    caselaw_highlight.importance = 4
    assert caselaw_highlight.importance_name == "Normal"
