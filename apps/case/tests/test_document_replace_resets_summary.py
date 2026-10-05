"""Replacing a document's file forgets the old file's AI summary.

generate_document_summary() leaves a document alone once it has a
summary, so a replaced file kept describing the bytes it no longer held.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.case.models import Document

pytestmark = pytest.mark.django_db


def _summarised(document):
    document.summary = "Describes the old file."
    document.ocr_status = "completed"
    document.ocr_text = "old text"
    document.page_count = 3
    document.save()
    return document


def _edit(client, document, **extra):
    data = {
        "matter": document.matter_id,
        "name": document.name,
        "category": document.category,
        "ai_context": "auto",
        "importance": document.importance,
    }
    data.update(extra)
    return client.post(reverse("case:documents-edit", args=[document.id]), data)


def test_new_upload_clears_summary(client_with_matter, document, pdf_file):
    _summarised(document)
    new_file = SimpleUploadedFile(
        "replacement.pdf", pdf_file.read(), content_type="application/pdf"
    )

    response = _edit(client_with_matter, document, file=new_file)

    assert response.status_code == 204
    document = Document.objects.get(pk=document.pk)
    assert document.summary is None
    assert document.ocr_status == "pending"
    assert document.ocr_text is None
    assert document.page_count is None


def test_metadata_edit_keeps_summary(client_with_matter, document):
    _summarised(document)

    response = _edit(client_with_matter, document, name="Renamed")

    assert response.status_code == 204
    document = Document.objects.get(pk=document.pk)
    assert document.name == "Renamed"
    assert document.summary == "Describes the old file."
    assert document.ocr_status == "completed"


def test_reset_extraction_forgets_everything_read_from_the_bytes(document):
    _summarised(document)
    document.ocr_error = "boom"
    document.ocr_pages_done = 2

    document.reset_extraction()

    assert document.summary is None
    assert document.ocr_status == "pending"
    assert document.ocr_text is None
    assert document.ocr_error is None
    assert document.ocr_processed_at is None
    assert document.page_count is None
    assert document.ocr_pages_done == 0
