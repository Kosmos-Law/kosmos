"""A matter with no Gmail label keeps the emails it holds.

Closing a matter clears its label and keeps its emails. Nothing short of the
confirmed Unlink action may remove them, and the Emails tab goes on listing
them.
"""

import pytest
from django.urls import reverse

from apps.mail import google
from apps.mail.models import Email

from .test_views import make_email

pytestmark = pytest.mark.django_db


@pytest.fixture
def queued(monkeypatch):
    """Record queued resyncs instead of hitting django-q / Gmail."""
    calls = []
    monkeypatch.setattr(
        "apps.mail.views._queue_resync", lambda matter: calls.append(matter.id)
    )
    return calls


@pytest.fixture
def closed_matter(matter):
    make_email(matter, "kept-1", subject="Kept after closing", attachments=[])
    matter.status = "Closed"
    matter.save()
    matter.refresh_from_db()
    assert matter.gmail_label_name is None
    return matter


def test_link_with_nothing_chosen_is_refused(client, closed_matter, fake_gmail, queued):
    response = client.post(
        reverse("case:emails-label-link", args=[closed_matter.id]), {"label_name": ""}
    )

    assert response.status_code == 200
    assert "Choose a label" in response.content.decode()
    assert queued == []
    assert Email.objects.filter(matter=closed_matter).count() == 1


def test_link_with_nothing_chosen_keeps_the_current_label(
    client, matter, fake_gmail, queued
):
    response = client.post(reverse("case:emails-label-link", args=[matter.id]), {})

    assert response.status_code == 200
    matter.refresh_from_db()
    assert matter.gmail_label_name == "Matters - Open/Smith"
    assert queued == []


def test_resync_leaves_a_matter_with_no_label_alone(closed_matter, fake_gmail):
    stats = google.resync_matter(closed_matter)

    assert stats["removed"] == 0
    assert Email.objects.filter(matter=closed_matter).count() == 1


def test_resync_by_id_leaves_a_matter_with_no_label_alone(closed_matter, fake_gmail):
    google.resync_matter_by_id(closed_matter.id)

    assert Email.objects.filter(matter=closed_matter).count() == 1


def test_emails_tab_lists_kept_emails_without_a_label(
    client, closed_matter, fake_gmail
):
    content = client.get(
        reverse("case:emails-index", args=[closed_matter.id])
    ).content.decode()

    assert "Kept after closing" in content
    assert "No Gmail label is linked to this matter" in content
    assert "Count: 1" in content


def test_emails_tab_with_no_label_and_no_emails_prompts_to_link(
    client, matter, fake_gmail
):
    matter.gmail_label_name = None
    matter.save(update_fields=["gmail_label_name"])

    content = client.get(
        reverse("case:emails-index", args=[matter.id])
    ).content.decode()

    assert "No Gmail label is linked to this matter yet" in content
    assert "emails-split" not in content
