"""Actions on a document's row and dialog: the category menu when the
document has a proceeding, retrying a failed OCR, reversing the importance
sort, and what the Edit Document dialog links to and asks."""

import json

import pytest
from django.urls import reverse

from apps.case.models import Document

pytestmark = pytest.mark.django_db


@pytest.fixture
def filed_document(document, proceeding):
    document.category = "Record"
    document.proceeding = proceeding
    document.save()
    return document


# ── Category from the row menu ───────────────────────────────────────────


def test_category_that_a_proceeding_rules_out_is_refused_with_a_reason(
    client, filed_document
):
    response = client.post(
        reverse("case:document-category", args=[filed_document.id, "Evidence"])
    )

    assert response.status_code == 200
    toast = json.loads(response["HX-Toast"])
    assert toast["type"] == "warning"
    assert "proceeding" in toast["message"]
    assert "—" not in toast["message"]
    filed_document.refresh_from_db()
    assert filed_document.category == "Record"
    assert filed_document.proceeding is not None


def test_discovery_is_allowed_with_a_proceeding(client, filed_document):
    response = client.post(
        reverse("case:document-category", args=[filed_document.id, "Discovery"])
    )

    assert "HX-Toast" not in response
    filed_document.refresh_from_db()
    assert filed_document.category == "Discovery"


def test_category_change_without_a_proceeding_has_no_warning(client, document):
    response = client.post(
        reverse("case:document-category", args=[document.id, "Correspondence"])
    )

    assert "HX-Toast" not in response
    document.refresh_from_db()
    assert document.category == "Correspondence"


# ── Retry a failed OCR ───────────────────────────────────────────────────


@pytest.fixture
def queued(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "django_q.tasks.async_task", lambda func, *args, **kwargs: calls.append(args)
    )
    return calls


def test_failed_badge_offers_retry(client, matter, document):
    Document.objects.filter(pk=document.pk).update(
        ocr_status="failed", ocr_error="tesseract crashed"
    )

    body = client.get(reverse("case:documents-list", args=[matter.id])).content.decode()

    assert "ocr failed" in body
    assert f'hx-post="{reverse("case:retry-ocr", args=[document.id])}"' in body


def test_retry_from_the_badge_queues_ocr_and_returns_the_pending_badge(
    client, document, queued
):
    Document.objects.filter(pk=document.pk).update(ocr_status="failed")

    response = client.post(
        reverse("case:retry-ocr", args=[document.id]),
        {"hide_on_bypass": "1"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert "ocr pending" in body
    assert "hide_on_bypass=1" in body  # keeps polling the way the row does
    assert queued == [(document.id,)]
    document.refresh_from_db()
    assert document.ocr_status == "pending"


# ── Importance sort ──────────────────────────────────────────────────────


def test_importance_sort_reverses_on_a_second_click(client, matter):
    key = f"documents_filter_{matter.id}"
    url = reverse("case:documents-sort", args=[matter.id, "-importance"])

    client.get(url)
    assert client.session[key]["order_by"] == "-importance"
    client.get(url)
    assert client.session[key]["order_by"] == "importance"
    client.get(url)
    assert client.session[key]["order_by"] == "-importance"


def test_other_columns_still_toggle(client, matter):
    key = f"documents_filter_{matter.id}"
    url = reverse("case:documents-sort", args=[matter.id, "date"])

    client.get(url)
    assert client.session[key]["order_by"] == "date"
    client.get(url)
    assert client.session[key]["order_by"] == "-date"
    client.get(url)
    assert client.session[key]["order_by"] == "date"


# ── Edit Document dialog ─────────────────────────────────────────────────


def test_edit_dialog_links_the_current_file_to_the_real_download(client, document):
    body = client.get(
        reverse("case:documents-edit", args=[document.id])
    ).content.decode()

    download = reverse("case:documents-download", args=[document.id])
    assert f'data-download-url="{download}"' in body
    assert client.get(download).status_code == 200


def test_delete_confirmation_says_document(client, document):
    body = client.get(
        reverse("case:documents-edit", args=[document.id])
    ).content.decode()

    assert "delete this document?" in body
    assert "delete this file?" not in body


def test_upload_errors_have_no_em_dash():
    import inspect

    from apps.case.documents import views

    assert "—" not in inspect.getsource(views.documents_add)
