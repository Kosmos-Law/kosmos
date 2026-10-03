"""Bulk actions on the Documents tab act only on documents of the matter in
the URL, whatever ids the session's selection holds, and a document that is
moved leaves the old matter's labels behind."""

import pytest
from django.urls import reverse

from apps.case.models import Document, Label
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


@pytest.fixture
def third_matter(user, contact, practice_area):
    return Matter.objects.create(
        user=user,
        name="Third Matter",
        status="Open",
        date_start="2024-01-01",
        practice_area=practice_area,
        client=contact,
    )


@pytest.fixture
def stray(user, other_matter):
    """A document on another matter whose id has got into the selection."""
    doc = Document(
        matter=other_matter,
        name="Not Selected Here",
        category="Evidence",
        created_by=user,
        ocr_status="not_applicable",
    )
    doc.save()
    return doc


@pytest.fixture
def selected(client, matter, document, stray):
    session = client.session
    session[f"selected_documents_{matter.id}"] = [document.id, stray.id]
    session.save()
    return client


def test_bulk_delete_ignores_a_document_on_another_matter(
    selected, matter, document, stray
):
    response = selected.post(reverse("case:documents-bulk-delete", args=[matter.id]))

    assert response.status_code == 204
    assert not Document.objects.filter(pk=document.pk).exists()
    assert Document.objects.filter(pk=stray.pk).exists()


def test_bulk_ai_ignores_a_document_on_another_matter(
    selected, matter, document, stray
):
    selected.post(reverse("case:documents-bulk-ai", args=[matter.id, "never"]))

    document.refresh_from_db()
    stray.refresh_from_db()
    assert document.ai_context == "never"
    assert stray.ai_context == "auto"


def test_bulk_importance_ignores_a_document_on_another_matter(
    selected, matter, document, stray
):
    selected.post(
        reverse("case:documents-bulk-importance", args=[matter.id]), {"importance": 7}
    )

    document.refresh_from_db()
    stray.refresh_from_db()
    assert document.importance == 7
    assert stray.importance == 4


def test_bulk_category_ignores_a_document_on_another_matter(
    selected, matter, document, stray
):
    selected.post(
        reverse("case:documents-bulk-category", args=[matter.id]),
        {"category": "Discovery"},
    )

    document.refresh_from_db()
    stray.refresh_from_db()
    assert document.category == "Discovery"
    assert stray.category == "Evidence"


def test_bulk_update_ignores_a_document_on_another_matter(
    selected, matter, document, stray, proceeding
):
    selected.post(
        reverse("case:documents-bulk-update", args=[matter.id]),
        {"proceeding": proceeding.id},
    )

    document.refresh_from_db()
    stray.refresh_from_db()
    assert document.proceeding == proceeding
    assert stray.proceeding is None


def test_bulk_move_ignores_a_document_on_another_matter(
    selected, matter, document, stray, other_matter, third_matter
):
    selected.post(
        reverse("case:documents-bulk-matter", args=[matter.id]),
        {"matter": third_matter.id},
    )

    document.refresh_from_db()
    stray.refresh_from_db()
    assert document.matter_id == third_matter.id
    assert stray.matter_id == other_matter.id


# ── Labels on a move ─────────────────────────────────────────────────────


@pytest.fixture
def labelled(document, label, global_label, other_matter):
    """The document carries its matter's label, a global one, and (so the
    rule is tested on the destination too) one of the target matter's."""
    target_label = Label.objects.create(matter=other_matter, name="Theirs", color="red")
    document.labels.add(label, global_label, target_label)
    return {"own": label, "global": global_label, "target": target_label}


def test_bulk_move_drops_the_old_matters_labels_and_keeps_global_ones(
    client, matter, other_matter, document, labelled
):
    session = client.session
    session[f"selected_documents_{matter.id}"] = [document.id]
    session.save()

    client.post(
        reverse("case:documents-bulk-matter", args=[matter.id]),
        {"matter": other_matter.id},
    )

    document.refresh_from_db()
    assert document.matter_id == other_matter.id
    assert set(document.labels.all()) == {labelled["global"], labelled["target"]}
    # The label itself is untouched; it only came off this document.
    assert Label.objects.filter(pk=labelled["own"].pk).exists()


def test_edit_details_move_drops_the_old_matters_labels(
    client, matter, other_matter, document, labelled
):
    response = client.post(
        reverse("case:documents-edit", args=[document.id]),
        {
            "matter": other_matter.id,
            "category": document.category,
            "name": document.name,
            "description": "",
            "date": "2024-01-20",
            "ai_context": "auto",
        },
    )

    assert response.status_code == 204
    document.refresh_from_db()
    assert document.matter_id == other_matter.id
    assert set(document.labels.all()) == {labelled["global"], labelled["target"]}


def test_edit_details_without_a_move_keeps_every_label(
    client, matter, document, label, global_label
):
    document.labels.add(label, global_label)

    client.post(
        reverse("case:documents-edit", args=[document.id]),
        {
            "matter": matter.id,
            "category": document.category,
            "name": "Renamed",
            "description": "",
            "date": "2024-01-20",
            "ai_context": "auto",
        },
    )

    assert set(document.labels.all()) == {label, global_label}
