"""The matter Emails tab on a server without Google sign-in.

Nobody can connect a mailbox until the OAuth client file is in place, so a
matter with no synced emails hides the tab. Emails synced before stay
reachable whatever the setup is now. The not-connected copy says each
person connects their own mailbox (it is not an admin job).
"""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.case.views import get_last_tab
from apps.mail.models import Email

pytestmark = pytest.mark.django_db

EMAILS_URL = 'hx-push-url="/case/{}/emails/"'


@pytest.fixture
def oauth_ready(monkeypatch):
    monkeypatch.setattr(
        "apps.settings.integrations.oauth.google_oauth_configured", lambda: True
    )


@pytest.fixture
def oauth_missing(monkeypatch):
    monkeypatch.setattr(
        "apps.settings.integrations.oauth.google_oauth_configured", lambda: False
    )


def _nav(client, matter):
    return client.get(f"/case/{matter.id}/tab/documents/").content.decode()


def _remember(client, matter, tab):
    session = client.session
    session[f"case_tab_{matter.id}"] = tab
    session.save()


def test_tab_hidden_without_oauth_or_emails(client, matter, oauth_missing):
    assert EMAILS_URL.format(matter.id) not in _nav(client, matter)


def test_tab_shown_when_oauth_is_set_up(client, matter, oauth_ready):
    assert EMAILS_URL.format(matter.id) in _nav(client, matter)


def test_tab_shown_for_a_matter_with_synced_emails(client, matter, oauth_missing):
    Email.objects.create(
        matter=matter,
        gmail_id="m1",
        thread_id="t1",
        subject="Kept",
        date=timezone.now(),
    )
    assert EMAILS_URL.format(matter.id) in _nav(client, matter)


def test_remembered_emails_tab_falls_back_when_hidden(client, matter, oauth_missing):
    _remember(client, matter, "emails")

    response = client.get(reverse("case:select-matter", args=[matter.id]))

    assert response["Location"] == reverse("case:documents-index", args=[matter.id])


def test_remembered_emails_tab_kept_when_shown(client, matter, oauth_ready):
    _remember(client, matter, "emails")

    response = client.get(reverse("case:select-matter", args=[matter.id]))

    assert response["Location"] == reverse("case:emails-index", args=[matter.id])


def test_get_last_tab_leaves_other_tabs_alone(rf, matter, oauth_missing):
    request = rf.get("/")
    request.session = {f"case_tab_{matter.id}": "notes"}
    assert get_last_tab(request, matter.id) == "notes"


def test_not_connected_copy_says_each_person_connects(client, matter, oauth_ready):
    body = client.get(reverse("case:emails-index", args=[matter.id])).content.decode()

    assert "Each person connects their own" in body
    assert "An admin can connect it" not in body


def test_label_modal_copy_says_each_person_connects(client, matter, oauth_ready):
    body = client.get(
        reverse("case:emails-label-link-modal", args=[matter.id])
    ).content.decode()

    assert "Each person connects their own" in body
    assert "An admin can connect it" not in body
