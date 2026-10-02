"""A document that came from Google Drive stays on the matter its Drive
folder is linked to: the sync would move it back. It cannot be moved from
Kosmos, by bulk move or by Edit Details. Hand-uploaded documents move as
before."""

import json

import pytest
from django.urls import reverse

from apps.case.models import Document
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_matter(user, contact, practice_area):
    return Matter.objects.create(
        user=user,
        name="Other Matter",
        status="Open",
        date_start="2024-01-01",
        practice_area=practice_area,
        client=contact,
    )


def _drive_document(matter, user, name, file_id):
    doc = Document(
        matter=matter,
        name=name,
        category="Evidence",
        created_by=user,
        ocr_status="not_applicable",
        drive_file_id=file_id,
        drive_path=f"Evidence/{name}.pdf",
    )
    doc.save()
    return doc


@pytest.fixture
def drive_document(matter, user, pdf_file):
    doc = _drive_document(matter, user, "From Drive", "drive-file-1")
    doc.file = pdf_file
    doc.save()
    return doc


def _select(client, matter, *documents):
    session = client.session
    session[f"selected_documents_{matter.id}"] = [d.id for d in documents]
    session.save()


def _bulk_move(client, matter, target):
    return client.post(
        reverse("case:documents-bulk-matter", args=[matter.id]), {"matter": target.id}
    )


def _edit_data(document, matter_id=None):
    data = {
        "category": document.category,
        "name": document.name,
        "description": "",
        "date": "2024-01-20",
        "ai_context": "auto",
    }
    if matter_id is not None:
        data["matter"] = matter_id
    return data


# ── Bulk move ────────────────────────────────────────────────────────────


def test_bulk_move_skips_a_drive_document_and_says_so(
    client, matter, other_matter, document, drive_document
):
    _select(client, matter, document, drive_document)

    response = _bulk_move(client, matter, other_matter)

    assert response.status_code == 204
    document.refresh_from_db()
    drive_document.refresh_from_db()
    assert document.matter_id == other_matter.id  # hand-uploaded: moved
    assert drive_document.matter_id == matter.id  # from Drive: left alone

    toast = json.loads(response["HX-Toast"])
    assert toast["type"] == "warning"
    assert toast["message"].startswith("1 document from Google Drive was not moved.")
    assert "folder in Google Drive" in toast["message"]
    assert "—" not in toast["message"]


def test_bulk_move_counts_every_skipped_document(
    client, user, matter, other_matter, drive_document
):
    second = _drive_document(matter, user, "Also From Drive", "drive-file-2")
    _select(client, matter, drive_document, second)

    response = _bulk_move(client, matter, other_matter)

    toast = json.loads(response["HX-Toast"])
    assert toast["message"].startswith("2 documents from Google Drive were not moved.")
    assert Document.objects.filter(matter=matter).count() == 2


def test_bulk_move_of_hand_uploaded_documents_has_no_warning(
    client, matter, other_matter, document
):
    _select(client, matter, document)

    response = _bulk_move(client, matter, other_matter)

    assert "HX-Toast" not in response
    document.refresh_from_db()
    assert document.matter_id == other_matter.id


# ── Edit Details ─────────────────────────────────────────────────────────


def test_edit_details_shows_the_matter_locked_for_a_drive_document(
    client, matter, other_matter, drive_document
):
    response = client.get(reverse("case:documents-edit", args=[drive_document.id]))

    form = response.context["form"]
    assert form.fields["matter"].disabled is True
    assert form["matter"].value() == matter.id
    body = response.content.decode()
    assert 'name="matter"' in body and "disabled" in form["matter"].as_widget()
    assert "This document follows its folder in Google Drive." in body
    assert "—" not in body


def test_edit_details_is_not_locked_for_a_hand_uploaded_document(
    client, matter, document
):
    response = client.get(reverse("case:documents-edit", args=[document.id]))

    assert response.context["form"].fields["matter"].disabled is False
    assert "follows its folder in Google Drive" not in response.content.decode()


def test_posted_change_to_a_drive_documents_matter_is_refused(
    client, matter, other_matter, drive_document
):
    data = _edit_data(drive_document, other_matter.id)
    data["name"] = "Renamed In The Same Request"

    response = client.post(
        reverse("case:documents-edit", args=[drive_document.id]), data
    )

    # The form comes back with the reason; nothing in the request is saved.
    assert response.status_code == 200
    assert "follows its folder in Google Drive" in response.content.decode()
    drive_document.refresh_from_db()
    assert drive_document.matter_id == matter.id
    assert drive_document.name == "From Drive"


def test_other_details_of_a_drive_document_still_save(client, matter, drive_document):
    # What the browser sends: a disabled field is left out of the request.
    data = _edit_data(drive_document)
    data["name"] = "Renamed"

    response = client.post(
        reverse("case:documents-edit", args=[drive_document.id]), data
    )

    assert response.status_code == 204
    drive_document.refresh_from_db()
    assert drive_document.name == "Renamed"
    assert drive_document.matter_id == matter.id


def test_edit_details_still_moves_a_hand_uploaded_document(
    client, matter, other_matter, document
):
    response = client.post(
        reverse("case:documents-edit", args=[document.id]),
        _edit_data(document, other_matter.id),
    )

    assert response.status_code == 204
    document.refresh_from_db()
    assert document.matter_id == other_matter.id
