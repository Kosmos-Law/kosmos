"""The OCR badge says when the background worker is stopped.

OCR runs in the worker, so a pending badge would otherwise poll every 3s
forever. While the worker looks down it reads "ocr paused" and stops polling.
"""

import pytest
from django.urls import reverse

from apps.case.models import Document

pytestmark = pytest.mark.django_db


def badge(client, document, monkeypatch, worker_down):
    monkeypatch.setattr(
        "apps.management.templatetags.worker_health.worker_looks_down",
        lambda: worker_down,
    )
    response = client.get(reverse("case:ocr-badge", args=[document.id]))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.parametrize("status", ["pending", "processing"])
def test_badge_says_paused_and_stops_polling_while_worker_is_down(
    client, document, monkeypatch, status
):
    Document.objects.filter(pk=document.pk).update(ocr_status=status)
    html = badge(client, document, monkeypatch, worker_down=True)
    assert "ocr paused" in html
    assert "hx-get" not in html


def test_pending_badge_polls_while_worker_runs(client, document, monkeypatch):
    Document.objects.filter(pk=document.pk).update(ocr_status="pending")
    html = badge(client, document, monkeypatch, worker_down=False)
    assert "ocr pending" in html
    assert "every 3s" in html


def test_failed_badge_ignores_the_worker(client, document, monkeypatch):
    Document.objects.filter(pk=document.pk).update(ocr_status="failed")
    html = badge(client, document, monkeypatch, worker_down=True)
    assert "ocr failed" in html
