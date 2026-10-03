"""Deleting a document or a label, and changing a document's category,
importance or proceeding, refuse a plain link (GET)."""

import pytest
from django.urls import reverse

from apps.case.models import Document, Label

pytestmark = pytest.mark.django_db


def test_get_does_not_delete_a_document(client, document):
    response = client.get(reverse("case:documents-delete", args=[document.id]))

    assert response.status_code == 405
    assert Document.objects.filter(pk=document.pk).exists()


@pytest.mark.parametrize("method", ["post", "delete"])
def test_document_delete_accepts_post_and_delete(client, document, method):
    response = getattr(client, method)(
        reverse("case:documents-delete", args=[document.id])
    )

    assert response.status_code == 204
    assert not Document.objects.filter(pk=document.pk).exists()


def test_get_does_not_delete_a_label(client, label):
    response = client.get(reverse("case:delete-label", args=[label.id]))

    assert response.status_code == 405
    assert Label.objects.filter(pk=label.pk).exists()


@pytest.mark.parametrize("method", ["post", "delete"])
def test_label_delete_accepts_post_and_delete(client, label, method):
    response = getattr(client, method)(reverse("case:delete-label", args=[label.id]))

    assert response.status_code == 204
    assert not Label.objects.filter(pk=label.pk).exists()


def test_get_does_not_change_category(client, document):
    response = client.get(
        reverse("case:document-category", args=[document.id, "Discovery"])
    )

    assert response.status_code == 405
    document.refresh_from_db()
    assert document.category == "Evidence"


def test_post_changes_category_and_returns_the_list(client, document):
    response = client.post(
        reverse("case:document-category", args=[document.id, "Discovery"])
    )

    assert response.status_code == 200
    assert b"documents-list" in response.content
    document.refresh_from_db()
    assert document.category == "Discovery"


def test_get_does_not_change_importance(client, document):
    response = client.get(reverse("case:document-importance", args=[document.id, 7]))

    assert response.status_code == 405
    document.refresh_from_db()
    assert document.importance == 4


def test_post_changes_importance(client, document):
    response = client.post(reverse("case:document-importance", args=[document.id, 7]))

    assert response.status_code == 200
    document.refresh_from_db()
    assert document.importance == 7


def test_get_does_not_change_proceeding(client, document, proceeding):
    response = client.get(
        reverse("case:document-proceeding", args=[document.id, proceeding.id])
    )

    assert response.status_code == 405
    document.refresh_from_db()
    assert document.proceeding is None


def test_row_menus_send_post(client, matter, document):
    body = client.get(reverse("case:documents-list", args=[matter.id])).content.decode()

    category = reverse("case:document-category", args=[document.id, "Record"])
    importance = reverse("case:document-importance", args=[document.id, 7])
    assert f'hx-post="{category}"' in body
    assert f'hx-post="{importance}"' in body
    assert f'hx-get="{category}"' not in body
    assert f'hx-get="{importance}"' not in body
