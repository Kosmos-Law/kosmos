"""A fact's sources and the labels applied in bulk come from the posted
body, which the URL-based matter check never sees. Only a document, a
highlight or a label on the same matter (or a global label) is accepted."""

import pytest

from apps.case.models import CaseLaw, Document, Highlight, Label
from apps.management.selection import get_session_key
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_matter(practice_area):
    return Matter.objects.create(
        name="Other Matter", status="Open", practice_area=practice_area
    )


@pytest.fixture
def other_document(other_matter, user):
    return Document.objects.create(
        matter=other_matter,
        name="Other matter's exhibit",
        category="Evidence",
        created_by=user,
        ocr_status="not_applicable",
    )


@pytest.fixture
def other_highlight(other_document, user):
    return Highlight.objects.create(
        document=other_document,
        slug="Other matter's passage",
        text="Privileged text from another matter.",
        page_number=3,
        created_by=user,
    )


@pytest.fixture
def other_label(other_matter):
    return Label.objects.create(matter=other_matter, name="Elsewhere", color="red")


def _select(client, prefix, matter, ids):
    session = client.session
    session[get_session_key(prefix, matter.id)] = ids
    session.save()


class TestFactSources:
    def test_another_matters_document_is_refused(self, client, fact, other_document):
        response = client.post(
            f"/case/facts/{fact.id}/sources/add/",
            {"type": "document", "id": other_document.id},
        )

        assert response.status_code == 404
        assert not fact.documents.exists()
        assert other_document.name.encode() not in response.content

    def test_another_matters_highlight_is_refused(self, client, fact, other_highlight):
        response = client.post(
            f"/case/facts/{fact.id}/sources/add/",
            {"type": "highlight", "id": other_highlight.id},
        )

        assert response.status_code == 404
        assert not fact.highlights.exists()

    def test_the_matters_own_sources_are_accepted(
        self, client, fact, document, highlight
    ):
        for kind, obj in (("document", document), ("highlight", highlight)):
            response = client.post(
                f"/case/facts/{fact.id}/sources/add/", {"type": kind, "id": obj.id}
            )
            assert response.status_code == 200

        assert list(fact.documents.all()) == [document]
        assert list(fact.highlights.all()) == [highlight]

    def test_a_highlight_on_the_matters_saved_case_is_accepted(
        self, client, fact, matter, user
    ):
        case_law = CaseLaw.objects.create(
            matter=matter, case_name="Roe v. Wade", citation="410 U.S. 113"
        )
        on_case = Highlight.objects.create(
            caselaw=case_law, slug="Holding", text="Held.", created_by=user
        )

        response = client.post(
            f"/case/facts/{fact.id}/sources/add/",
            {"type": "highlight", "id": on_case.id},
        )

        assert response.status_code == 200
        assert list(fact.highlights.all()) == [on_case]

    def test_a_malformed_id_is_a_404_not_an_error(self, client, fact):
        response = client.post(
            f"/case/facts/{fact.id}/sources/add/", {"type": "document", "id": "x"}
        )

        assert response.status_code == 404

    def test_removing_looks_only_among_the_facts_own_sources(
        self, client, fact, document, other_document
    ):
        fact.documents.add(document)

        refused = client.post(
            f"/case/facts/{fact.id}/sources/remove/",
            {"type": "document", "id": other_document.id},
        )
        removed = client.post(
            f"/case/facts/{fact.id}/sources/remove/",
            {"type": "document", "id": document.id},
        )

        assert refused.status_code == 404
        assert removed.status_code == 200
        assert not fact.documents.exists()


class TestBulkLabels:
    def test_facts_refuse_another_matters_label(
        self, client, matter, fact, other_label
    ):
        _select(client, "selected_facts", matter, [fact.id])

        response = client.post(
            f"/case/{matter.id}/facts/bulk-label-action/",
            {"label_id": other_label.id, "action": "add"},
        )

        assert response.status_code == 404
        assert not fact.labels.exists()

    def test_facts_accept_the_matters_label_and_a_global_one(
        self, client, matter, fact, label, global_label
    ):
        _select(client, "selected_facts", matter, [fact.id])

        for item in (label, global_label):
            response = client.post(
                f"/case/{matter.id}/facts/bulk-label-action/",
                {"label_id": item.id, "action": "add"},
            )
            assert response.status_code == 200

        assert set(fact.labels.all()) == {label, global_label}

    def test_highlights_refuse_another_matters_label(
        self, client, matter, highlight, other_label
    ):
        _select(client, "selected_highlights", matter, [highlight.id])

        response = client.post(
            f"/case/{matter.id}/highlights/bulk-label-action/",
            {"label_id": other_label.id, "action": "add"},
        )

        assert response.status_code == 404
        assert not highlight.labels.exists()

    def test_highlights_accept_the_matters_label_and_a_global_one(
        self, client, matter, highlight, label, global_label
    ):
        _select(client, "selected_highlights", matter, [highlight.id])

        for item in (label, global_label):
            response = client.post(
                f"/case/{matter.id}/highlights/bulk-label-action/",
                {"label_id": item.id, "action": "add"},
            )
            assert response.status_code == 200

        assert set(highlight.labels.all()) == {label, global_label}
