"""The bulk Category and Importance actions apply the checks the single
document's menus do; Add Document files under the matter chosen in the form;
and taking a label off needs a POST."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.case.models import Document
from apps.case.tests.test_document_fingerprint import make_pdf
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def selected(client_with_matter, matter, document):
    session = client_with_matter.session
    session[f"selected_documents_{matter.id}"] = [document.id]
    session.save()
    return client_with_matter


# --- bulk importance -----------------------------------------------------------


@pytest.mark.parametrize("value", ["high", "0", "8", "-1"])
def test_bulk_importance_refuses_a_value_outside_the_seven_levels(
    selected, matter, document, value
):
    url = reverse("case:documents-bulk-importance", args=[matter.id])

    response = selected.post(url, {"importance": value})

    assert response.status_code == 400
    document.refresh_from_db()
    assert document.importance == 4


def test_bulk_importance_sets_a_level(selected, matter, document):
    url = reverse("case:documents-bulk-importance", args=[matter.id])

    selected.post(url, {"importance": "6"})

    document.refresh_from_db()
    assert document.importance == 6


# --- bulk category -------------------------------------------------------------


def test_bulk_category_refuses_an_unknown_category(selected, matter, document):
    url = reverse("case:documents-bulk-category", args=[matter.id])

    response = selected.post(url, {"category": "Gossip"})

    assert response.status_code == 400
    document.refresh_from_db()
    assert document.category == "Evidence"


def test_bulk_category_leaves_a_document_filed_under_a_proceeding(
    selected, matter, document, proceeding
):
    Document.objects.filter(pk=document.pk).update(
        category="Record", proceeding=proceeding
    )
    url = reverse("case:documents-bulk-category", args=[matter.id])

    response = selected.post(url, {"category": "Correspondence"})

    document.refresh_from_db()
    assert document.category == "Record"
    assert document.proceeding == proceeding
    assert "1 document was not changed" in response["HX-Toast"]


def test_bulk_category_may_make_it_discovery(selected, matter, document, proceeding):
    Document.objects.filter(pk=document.pk).update(
        category="Record", proceeding=proceeding
    )
    url = reverse("case:documents-bulk-category", args=[matter.id])

    response = selected.post(url, {"category": "Discovery"})

    document.refresh_from_db()
    assert document.category == "Discovery"
    assert "HX-Toast" not in response


# --- Add Document's Matter field -------------------------------------------------


def test_add_document_files_under_the_matter_chosen_in_the_form(
    client_with_matter, matter, user, contact, practice_area, proceeding, label
):
    other = Matter.objects.create(
        user=user,
        name="Other Matter",
        status="Open",
        date_start="2024-01-01",
        practice_area=practice_area,
        client=contact,
    )
    data = {
        "matter": other.id,
        "category": "Record",
        "proceeding": proceeding.id,
        "labels": [label.id],
        "name": "Upload",
        "ai_context": "auto",
        "file": SimpleUploadedFile("x.pdf", make_pdf(), content_type="application/pdf"),
    }

    response = client_with_matter.post(
        reverse("case:documents-add", args=[matter.id]), data
    )

    assert response.status_code == 204
    doc = Document.objects.get()
    assert doc.matter == other
    # The proceeding and the label belong to the matter the form was opened
    # from: neither follows the document to another matter.
    assert doc.proceeding is None
    assert not doc.labels.exists()


# --- labels ----------------------------------------------------------------------


def test_removing_a_label_needs_a_post(client_with_matter, document, label):
    document.labels.add(label)
    url = reverse("case:remove-label-from", args=["document", document.id])

    response = client_with_matter.get(url, {"label_id": label.id})

    assert response.status_code == 405
    assert list(document.labels.all()) == [label]
