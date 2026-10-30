"""Apply Labels refreshes the row it was opened from.

A table row cannot be sent back beside the dialog (the browser drops a bare
<tr>, so the row was not refreshed and its cells landed in the dialog). For
those the list is told to reload instead.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _apply(client, object_type, obj, label, **extra):
    return client.post(
        reverse("case:labels-apply-modal-action", args=[object_type, obj.id]),
        {"label_id": label.id, "action": "add", **extra},
    )


def test_document_row_is_refreshed_through_the_list(client, document, label):
    response = _apply(client, "document", document, label)

    assert response.status_code == 200
    assert response["HX-Trigger"] == "documentsChanged"
    body = response.content.decode()
    assert "Apply Labels" in body
    assert "<tr" not in body
    assert label in document.labels.all()


def test_fact_row_is_refreshed_through_the_list(client, fact, label):
    response = _apply(client, "fact", fact, label)

    assert response["HX-Trigger"] == "factsChanged"
    assert "<tr" not in response.content.decode()


def test_notes_take_no_labels(client, label):
    response = client.post(
        reverse("case:labels-apply-modal-action", args=["note", 1]),
        {"label_id": label.id, "action": "add"},
    )

    assert response.status_code == 400


def test_highlight_table_row_is_refreshed_through_the_list(client, highlight, label):
    response = _apply(client, "highlight", highlight, label, view="table")

    assert response["HX-Trigger"] == "highlightsChanged"
    assert "<tr" not in response.content.decode()


def test_highlight_card_is_still_swapped_out_of_band(client, highlight, label):
    response = _apply(client, "highlight", highlight, label)

    assert "HX-Trigger" not in response
    body = response.content.decode()
    assert f'id="highlight-{highlight.id}"' in body
    assert 'hx-swap-oob="true"' in body
