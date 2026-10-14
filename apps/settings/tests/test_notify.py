"""Notifications by ntfy: the default channel, the push settings, what is
pushed, and the fall back to email."""

from datetime import date, time

import pytest
import requests
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.calendar.models import Event
from utils import notify

pytestmark = pytest.mark.django_db


class FakeNtfy:
    """Stands in for ntfy's server: records each publish, or fails."""

    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def post(self, url, json=None, headers=None, timeout=None):
        if self.fail:
            raise requests.ConnectionError("ntfy is down")
        self.sent.append({"url": url, "json": json, "headers": headers or {}})

        class Response:
            def raise_for_status(self):
                pass

        return Response()


@pytest.fixture
def ntfy(monkeypatch):
    fake = FakeNtfy()
    monkeypatch.setattr(notify.requests, "post", fake.post)
    return fake


@pytest.fixture
def ntfy_down(monkeypatch):
    fake = FakeNtfy(fail=True)
    monkeypatch.setattr(notify.requests, "post", fake.post)
    return fake


@pytest.fixture(autouse=True)
def _production_like(settings):
    """Pushes and email as production sends them; the dev-only marks are
    tested on their own."""
    settings.NTFY_TOPIC_SUFFIX = ""
    settings.NOTIFY_TITLE_PREFIX = ""
    settings.EMAIL_NOTIFICATIONS = True
    settings.PUBLIC_BASE_URL = "https://kosmos.example.com"


@pytest.fixture
def ntfy_user(user, client):
    # An update, not a save: the fixture's user is stale once the client
    # has opened the dash, and saving it would undo that
    CustomUser.objects.filter(pk=user.pk).update(
        notify_by="ntfy", ntfy_topic="kosmos-secret-topic"
    )
    user.refresh_from_db()
    return user


@pytest.fixture
def event(user, matter):
    return Event.objects.create(
        user=user,
        matter=matter,
        date=date(2030, 3, 4),
        start_time=time(9, 0),
        end_time=time(9, 30),
        description="Status conference",
        location="Courtroom 4",
        status="Pending",
    )


# --- the setting -----------------------------------------------------------


def test_the_page_opens(client):
    response = client.get(reverse("settings:notifications-index"))

    assert response.status_code == 200
    assert "Set Up Push" in response.content.decode()


def test_choosing_push_gives_a_long_random_topic(client, user):
    client.post(reverse("settings:notify-by"), {"notify_by": "ntfy"})

    user.refresh_from_db()
    assert user.notify_by == "ntfy"
    assert user.ntfy_topic.startswith("kosmos-") and len(user.ntfy_topic) > 30


def test_an_unknown_channel_changes_nothing(client, user):
    client.post(reverse("settings:notify-by"), {"notify_by": "home"})

    user.refresh_from_db()
    assert user.notify_by == "email"
    assert user.ntfy_topic == ""


def test_choosing_push_again_keeps_the_topic(client, ntfy_user):
    client.post(reverse("settings:notify-by"), {"notify_by": "email"})
    client.post(reverse("settings:notify-by"), {"notify_by": "ntfy"})

    ntfy_user.refresh_from_db()
    assert ntfy_user.ntfy_topic == "kosmos-secret-topic"


def test_setting_up_push_makes_a_topic_without_changing_the_default(client, user):
    client.post(reverse("settings:ntfy-new-topic"))

    user.refresh_from_db()
    assert user.ntfy_topic.startswith("kosmos-")
    assert user.notify_by == "email"


def test_a_new_topic_replaces_the_old(client, ntfy_user):
    client.post(reverse("settings:ntfy-new-topic"))

    ntfy_user.refresh_from_db()
    assert ntfy_user.ntfy_topic != "kosmos-secret-topic"


def test_the_server_must_be_an_address(client, ntfy_user):
    response = client.post(reverse("settings:ntfy"), {"ntfy_server": "not a url"})

    assert "Enter the server" in response.content.decode()
    ntfy_user.refresh_from_db()
    assert ntfy_user.ntfy_server == "https://ntfy.sh"


def test_the_server_and_token_are_saved(client, ntfy_user):
    client.post(
        reverse("settings:ntfy"),
        {"ntfy_server": "https://push.example.com/", "ntfy_token": "tk_abc"},
    )

    ntfy_user.refresh_from_db()
    assert ntfy_user.ntfy_server == "https://push.example.com"
    assert ntfy_user.ntfy_token == "tk_abc"


def test_the_page_offers_the_subscribe_link_and_code(client, ntfy_user):
    page = client.get(reverse("settings:notifications-index")).content.decode()

    assert "ntfy://ntfy.sh/kosmos-secret-topic" in page
    assert "<svg" in page


def test_off_production_the_topic_carries_the_suffix(settings, client, ntfy_user):
    settings.NTFY_TOPIC_SUFFIX = "-dev"
    settings.NOT_PRODUCTION = True

    page = client.get(reverse("settings:notifications-index")).content.decode()

    assert "kosmos-secret-topic-dev" in page
    assert "not the production server" in page


def test_a_test_is_pushed_with_the_saved_token(client, ntfy_user, ntfy):
    response = client.post(
        reverse("settings:ntfy-test"),
        {"ntfy_server": "https://push.example.com/", "ntfy_token": "tk_abc"},
    )

    assert response["Location"].endswith("?test=sent")
    sent = ntfy.sent[0]
    assert sent["url"] == "https://push.example.com"
    assert sent["json"]["topic"] == "kosmos-secret-topic"
    assert sent["json"]["title"] == "Kosmos: notifications are working"
    assert sent["headers"]["Authorization"] == "Bearer tk_abc"


def test_a_failed_test_says_why(client, ntfy_user, ntfy_down):
    response = client.post(reverse("settings:ntfy-test"), {})

    assert response["Location"].endswith("?test=failed")
    page = client.get(response["Location"]).content.decode()
    assert "could not be sent" in page
    assert "ntfy is down" in page


# --- what is pushed ----------------------------------------------------------


def test_an_event_reminder_is_pushed(ntfy_user, ntfy, event, mailoutbox):
    assert notify.event_reminder(ntfy_user, event) == {"success": True}

    message = ntfy.sent[0]["json"]
    assert message["title"] == "Status conference"
    assert message["message"] == (
        "Monday, March 4 at 9:00 AM – 9:30 AM\nSample Test Matter\nCourtroom 4"
    )
    assert message["priority"] == 4
    assert message["click"] == "https://kosmos.example.com/events/"
    assert message["actions"] == [
        {
            "action": "view",
            "label": "Open",
            "url": "https://kosmos.example.com/events/",
        }
    ]
    assert mailoutbox == []


def test_off_production_pushes_are_marked(settings, ntfy_user, ntfy, event):
    settings.NTFY_TOPIC_SUFFIX = "-dev"
    settings.NOTIFY_TITLE_PREFIX = "[dev] "

    notify.event_reminder(ntfy_user, event)

    message = ntfy.sent[0]["json"]
    assert message["topic"] == "kosmos-secret-topic-dev"
    assert message["title"] == "[dev] Status conference"


def test_without_a_public_address_the_push_has_no_buttons(
    settings, ntfy_user, ntfy, event
):
    settings.PUBLIC_BASE_URL = ""

    notify.event_reminder(ntfy_user, event)

    message = ntfy.sent[0]["json"]
    assert "click" not in message
    assert "actions" not in message


def test_the_channel_named_on_the_notification_wins(ntfy_user, ntfy, event, mailoutbox):
    notify.event_reminder(ntfy_user, event, channel="email")

    assert ntfy.sent == []
    assert mailoutbox[0].to == ["testuser@example.com"]


def test_a_push_that_fails_goes_by_email(ntfy_user, ntfy_down, event, mailoutbox):
    assert notify.event_reminder(ntfy_user, event) == {"success": True}

    assert (
        mailoutbox[0].subject
        == "Status conference - Monday, March 4 at 9:00 AM – 9:30 AM"
    )
    assert "https://kosmos.example.com/events/" in mailoutbox[0].body


def test_a_user_without_a_topic_is_emailed(user, ntfy, event, mailoutbox):
    CustomUser.objects.filter(pk=user.pk).update(notify_by="ntfy")
    user.refresh_from_db()

    notify.event_reminder(user, event)

    assert ntfy.sent == []
    assert len(mailoutbox) == 1


def test_with_email_off_a_failed_push_is_reported(
    settings, ntfy_user, ntfy_down, event, mailoutbox
):
    settings.EMAIL_NOTIFICATIONS = False

    result = notify.event_reminder(ntfy_user, event)

    assert result["success"] is False
    assert mailoutbox == []


def test_with_email_off_nothing_is_emailed(settings, user, event, mailoutbox):
    settings.EMAIL_NOTIFICATIONS = False

    assert notify.event_reminder(user, event)["success"] is True
    assert mailoutbox == []


def test_a_user_without_an_address_cannot_be_emailed(user, event):
    CustomUser.objects.filter(pk=user.pk).update(email="")
    user.refresh_from_db()

    assert notify.event_reminder(user, event)["success"] is False
