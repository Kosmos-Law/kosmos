"""The Emails tab keeps itself up to date: the wrapper that reloads the list
is there however the tab was reached, Clear Filters leaves no filter behind,
the list column follows a Promote or an importance change, and the Gmail
link is offered only to the user whose mailbox it opens."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.mail.models import GmailAccount

from .test_views import make_email

pytestmark = pytest.mark.django_db


# ── The reload wrapper ───────────────────────────────────────────────────


def test_tab_click_renders_the_wrapper_that_listens_for_changes(
    client, matter, fake_gmail
):
    make_email(matter, "m1", attachments=[])

    body = client.get(f"/case/{matter.id}/tab/emails/").content.decode()

    assert 'id="emails"' in body
    assert 'hx-trigger="emailsChanged from:body"' in body
    assert reverse("case:emails-list", args=[matter.id]) in body


# ── Clear Filters ────────────────────────────────────────────────────────


def test_clear_filters_stores_no_filter(client, matter, fake_gmail):
    url = reverse("case:emails-filter", args=[matter.id])
    client.post(url, {"sender": "carol"})

    response = client.post(url, {"reset": "true"})

    assert response.status_code == 204
    assert client.session[f"emails_filter_{matter.id}"] == {}


def test_cleared_filter_does_not_read_as_active(client, matter, fake_gmail):
    client.post(reverse("case:emails-filter", args=[matter.id]), {"reset": "true"})

    response = client.get(reverse("case:emails-list", args=[matter.id]))

    assert response.context["filters_active"] is False
    # With no emails the tab says so, rather than blaming a filter.
    assert "No emails match the current filters" not in response.content.decode()


def test_a_leftover_reset_key_is_not_a_filter(client, matter, fake_gmail):
    session = client.session
    session[f"emails_filter_{matter.id}"] = {"reset": "true"}
    session.save()

    response = client.get(reverse("case:emails-list", args=[matter.id]))

    assert response.context["filters_active"] is False


def test_a_real_filter_still_reads_as_active(client, matter, fake_gmail):
    client.post(reverse("case:emails-filter", args=[matter.id]), {"sender": "carol"})

    response = client.get(reverse("case:emails-list", args=[matter.id]))

    assert response.context["filters_active"] is True


# ── The list column after a change ───────────────────────────────────────


def test_importance_change_tells_the_list_column_to_reload(client, matter, fake_gmail):
    email = make_email(matter, "m1", attachments=[])

    response = client.post(reverse("case:email-importance", args=[email.id, 7]))

    assert response["HX-Trigger"] == "emailItemsChanged"


def test_opening_an_email_does_not_reload_the_list(client, matter, fake_gmail):
    email = make_email(matter, "m1", attachments=[])

    response = client.get(reverse("case:email-preview", args=[email.id]))

    assert "HX-Trigger" not in response


def test_list_column_listens_and_reloads_alone(client, matter, fake_gmail):
    email = make_email(matter, "m1", attachments=[])
    items_url = reverse("case:emails-list-items", args=[matter.id])

    tab = client.get(reverse("case:emails-list", args=[matter.id])).content.decode()
    assert f'hx-get="{items_url}"' in tab
    assert 'hx-trigger="emailItemsChanged from:body"' in tab

    client.post(reverse("case:email-importance", args=[email.id, 7]))
    items = client.get(items_url).content.decode()
    assert "email-list-item importance-7" in items
    assert "email-preview" in items  # each row still opens the reading pane
    assert "emails-split" not in items  # the column only, not the tab


def test_promote_tells_the_list_column_to_reload(
    client, matter, fake_gmail, settings, tmp_path, monkeypatch
):
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
    settings.MEDIA_ROOT = str(tmp_path)
    monkeypatch.setattr("apps.mail.promote.async_task", lambda *args, **kwargs: None)
    # 01:30 UTC on the 6th is the evening of the 5th in New York.
    email = make_email(
        matter,
        "m1",
        attachments=[],
        date=datetime(2026, 1, 6, 1, 30, tzinfo=UTC),
    )

    with timezone.override(ZoneInfo("America/New_York")):
        response = client.post(reverse("case:email-promote", args=[email.id]))

    assert response["HX-Trigger"] == "emailItemsChanged"
    email.refresh_from_db()
    # The promoted document carries the local day the email was sent.
    assert str(email.document.date) == "2026-01-05"


# ── The Gmail link ───────────────────────────────────────────────────────


def _colleague_account():
    colleague = CustomUser.objects.create(username="colleague", user_rate=100)
    return GmailAccount.objects.create(
        user=colleague, address="colleague@example.com", token='{"token": "t"}'
    )


def _preview(client, email):
    return client.get(reverse("case:email-preview", args=[email.id])).content.decode()


def test_gmail_link_is_offered_for_the_users_own_mailbox(client, matter, fake_gmail):
    email = make_email(matter, "m1", account=fake_gmail.account, attachments=[])

    assert "mail/u/primary@example.com/#all/m1" in _preview(client, email)


def test_gmail_link_is_not_offered_into_a_colleagues_mailbox(
    client, matter, fake_gmail
):
    email = make_email(matter, "c1", account=_colleague_account(), attachments=[])

    body = _preview(client, email)

    assert "mail.google.com" not in body
    assert "Promote to Document" in body  # the rest of the pane is unchanged


def test_gmail_link_uses_the_users_own_copy_of_the_same_message(
    client, matter, fake_gmail
):
    shown = make_email(
        matter,
        "c1",
        account=_colleague_account(),
        message_id="<same@example.com>",
        attachments=[],
    )
    make_email(
        matter,
        "own1",
        account=fake_gmail.account,
        message_id="<same@example.com>",
        attachments=[],
    )

    body = _preview(client, shown)

    assert "mail/u/primary@example.com/#all/own1" in body
    assert "colleague@example.com" not in body
