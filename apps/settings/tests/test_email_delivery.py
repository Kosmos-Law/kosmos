"""Email that does not leave the server must not be reported as sent.

In console mode (EMAIL_BACKEND=console) every send succeeds without
reaching anyone, so admins get a banner, send confirmations say the
message was only logged, and the digest's Send Test reports a mail
server failure instead of raising a 500.
"""

import json
from smtplib import SMTPException
from unittest import mock

import pytest
from django.http import HttpResponse
from django.test import override_settings
from django.urls import reverse

from apps.intakes.models import Note
from utils.mail import NOT_DELIVERED_MESSAGE, email_delivers
from utils.toasts import toast_email_sent

pytestmark = pytest.mark.django_db

CONSOLE = "django.core.mail.backends.console.EmailBackend"
BANNER = b'class="email-banner"'


@pytest.mark.parametrize(
    ("backend", "delivers"),
    [
        ("django.core.mail.backends.smtp.EmailBackend", True),
        # The test runner's backend stands in for a real one.
        ("django.core.mail.backends.locmem.EmailBackend", True),
        (CONSOLE, False),
        ("django.core.mail.backends.dummy.EmailBackend", False),
    ],
)
def test_email_delivers_by_backend(backend, delivers):
    with override_settings(EMAIL_BACKEND=backend):
        assert email_delivers() is delivers


def test_send_toast_claims_delivery_only_when_mail_goes_out():
    toast = json.loads(toast_email_sent(HttpResponse(), "Sent")["HX-Toast"])
    assert (toast["type"], toast["message"]) == ("success", "Sent")

    with override_settings(EMAIL_BACKEND=CONSOLE):
        toast = json.loads(toast_email_sent(HttpResponse(), "Sent")["HX-Toast"])
    assert (toast["type"], toast["message"]) == ("warning", NOT_DELIVERED_MESSAGE)


# --- Admin banner ------------------------------------------------------------


@override_settings(EMAIL_BACKEND=CONSOLE)
def test_banner_shows_admins_when_email_is_not_delivered(admin_client):
    response = admin_client.get("/dash/")
    assert BANNER in response.content
    assert b"Outbound email is not configured" in response.content


@override_settings(EMAIL_BACKEND=CONSOLE)
def test_banner_hidden_from_non_admins(client):
    response = client.get("/dash/")
    assert response.status_code == 200
    assert BANNER not in response.content


def test_banner_hidden_when_email_delivers(admin_client):
    response = admin_client.get("/dash/")
    assert response.status_code == 200
    assert BANNER not in response.content


@override_settings(EMAIL_BACKEND=CONSOLE, DEBUG=True)
def test_banner_hidden_on_a_development_machine(admin_client):
    assert BANNER not in admin_client.get("/dash/").content


# --- Sends in console mode -----------------------------------------------------


@override_settings(EMAIL_BACKEND=CONSOLE)
def test_intake_email_in_console_mode_says_it_was_only_logged(client, intake):
    response = client.post(
        f"/intakes/{intake.id}/send-email/send",
        {"subject": "Regarding your inquiry", "body": "Dear Mr. Gandhi"},
    )
    assert response.status_code == 204
    toast = json.loads(response["HX-Toast"])
    assert toast["type"] == "warning"
    assert toast["message"] == NOT_DELIVERED_MESSAGE

    note = Note.objects.get(intake=intake)
    assert note.type == "Email Out"
    assert note.details.startswith("**Not delivered.**")
    assert "Regarding your inquiry" in note.details


def test_intake_email_note_unmarked_when_delivered(client, intake):
    client.post(
        f"/intakes/{intake.id}/send-email/send",
        {"subject": "Regarding your inquiry", "body": "Dear Mr. Gandhi"},
    )
    note = Note.objects.get(intake=intake)
    assert note.details.startswith("**Subject:**")


# --- Digest Send Test ------------------------------------------------------------


@pytest.fixture
def digest_user(user):
    user.digest_enabled = True
    user.save(update_fields=["digest_enabled"])
    return user


def test_send_test_digest_failure_is_an_error_toast_not_a_500(client, digest_user):
    with mock.patch(
        "apps.settings.notifications.views.send_digest_for_user",
        side_effect=SMTPException("connection refused"),
    ):
        response = client.post(reverse("settings:send-test-digest"))

    assert response.status_code == 200
    toast = json.loads(response["HX-Toast"])
    assert toast["type"] == "error"
    assert "connection refused" in toast["message"]
    assert b"connection refused" in response.content


@override_settings(EMAIL_BACKEND=CONSOLE)
def test_send_test_digest_in_console_mode_says_it_was_only_logged(client, digest_user):
    with mock.patch(
        "apps.settings.notifications.views.send_digest_for_user", return_value=True
    ):
        response = client.post(reverse("settings:send-test-digest"))

    assert b"logged on the server instead of sent" in response.content
    assert b"Test digest sent" not in response.content
