"""Full Cases (the matter's saved cases) and the case viewer."""

import json
from datetime import date

import pytest

from apps.case import courtlistener
from apps.case.courtlistener import OpinionResult
from apps.case.models import CaseLaw

pytestmark = pytest.mark.django_db


@pytest.fixture
def saved_cases(matter):
    return [
        CaseLaw.objects.create(
            matter=matter,
            case_name="Roe v. Wade",
            citation="410 U.S. 113",
            cluster_id=1,
            date_filed=date(1973, 1, 22),
        ),
        CaseLaw.objects.create(
            matter=matter,
            case_name="Birg v. Emory Healthcare",
            citation="300 Ga. App. 1",
            cluster_id=2,
        ),
    ]


class TestSearchCases:
    def _names(self, response):
        return sorted(c.case_name for c in response.context["case_laws"])

    def test_the_search_box_filters_by_name(self, client, matter, saved_cases):
        response = client.get(f"/case/{matter.id}/caselaws/list/", {"keyword": "birg"})

        assert self._names(response) == ["Birg v. Emory Healthcare"]

    def test_it_filters_by_citation_too(self, client, matter, saved_cases):
        response = client.get(f"/case/{matter.id}/caselaws/list/", {"keyword": "U.S."})

        assert self._names(response) == ["Roe v. Wade"]

    def test_the_text_is_kept_until_it_is_cleared(self, client, matter, saved_cases):
        client.get(f"/case/{matter.id}/caselaws/list/", {"keyword": "birg"})

        kept = client.get(f"/case/{matter.id}/caselaws/list/")
        assert self._names(kept) == ["Birg v. Emory Healthcare"]
        assert 'value="birg"' in kept.content.decode()

        cleared = client.get(f"/case/{matter.id}/caselaws/list/", {"keyword": ""})
        assert len(self._names(cleared)) == 2

    def test_no_match_says_so(self, client, matter, saved_cases):
        response = client.get(f"/case/{matter.id}/caselaws/list/", {"keyword": "zzz"})

        html = response.content.decode()
        assert "No saved cases match" in html
        assert "No case law added yet" not in html

    def test_the_box_swaps_only_the_table(self, client, matter, saved_cases):
        """Replacing the whole list would take the box, and the caret, away
        from someone still typing."""
        html = client.get(f"/case/{matter.id}/caselaws/list/").content.decode()

        box = html.split('id="caselaws-keyword-input"')[1].split(">")[0]
        assert 'hx-target="#caselaws-table"' in box
        assert 'hx-select="#caselaws-table"' in box


def test_saving_a_case_already_saved_closes_the_dialog_and_says_so(
    client, matter, saved_cases
):
    session = client.session
    session[f"caselaw_lookup_{matter.id}"] = {
        "found": True,
        "case_name": "Roe v. Wade",
        "citation": "410 U.S. 113",
        "cluster_id": 1,
    }
    session.save()

    response = client.post(f"/case/{matter.id}/caselaws/save/")

    assert response.status_code == 204
    assert "HX-Redirect" not in response.headers
    assert response.headers["HX-Trigger"] == "caselawsChanged"
    assert "already saved" in json.loads(response.headers["HX-Toast"])["message"]
    assert CaseLaw.objects.filter(matter=matter, cluster_id=1).count() == 1


class TestViewerForAnUnsavedCase:
    @pytest.fixture
    def html(self, client, matter, monkeypatch):
        monkeypatch.setattr(
            courtlistener,
            "fetch_cluster",
            lambda cluster_id: {
                "case_name": "Birg v. Emory Healthcare",
                "citations": [],
                "sub_opinions": ["https://api/opinions/90/"],
                "absolute_url": "/opinion/90/birg/",
            },
        )
        monkeypatch.setattr(
            courtlistener,
            "fetch_opinion",
            lambda opinion_id: OpinionResult(
                found=True, plain_text="The opinion.", html_with_citations=""
            ),
        )
        response = client.get(f"/case/{matter.id}/viewer/cluster/4242/")
        assert response.status_code == 200
        return response.content.decode()

    def test_the_page_script_is_valid(self, html):
        assert "caselawId: null," in html
        assert "caselawId: ," not in html

    def test_the_highlighter_is_visibly_off(self, html):
        button = html.split('id="createHighlightBtn"')[1].split(">")[0]
        assert "disabled" in button
        assert "Save this case to the matter" in button
        assert "not saved to the matter" in html


def test_the_viewer_for_a_saved_case_keeps_its_highlighter(client, matter, user):
    case_law = CaseLaw.objects.create(
        matter=matter,
        case_name="Roe v. Wade",
        citation="410 U.S. 113",
        text="The opinion of the court. " * 40,
        created_by=user,
    )

    html = client.get(f"/case/caselaws/{case_law.id}/view/").content.decode()

    assert f"caselawId: {case_law.id}," in html
    button = html.split('id="createHighlightBtn"')[1].split(">")[0]
    assert "disabled" not in button
