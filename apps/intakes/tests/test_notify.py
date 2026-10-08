import pytest
from django.core import mail
from django.test import Client

from apps.accounts.models import CustomUser
from apps.intakes.models import Intake
from apps.intakes.notify import notify_new_intake

pytestmark = pytest.mark.django_db


def make_user(username, **fields):
    fields.setdefault("email", f"{username}@example.com")
    fields.setdefault("notify_new_intakes", True)
    user = CustomUser.objects.create(username=username, user_rate=100, **fields)
    user.set_password("pw")
    user.save()
    return user


@pytest.fixture
def coordinator():
    return make_user("coordinator", first_name="Casey", last_name="Lee")


def test_manual_add_emails_the_coordinator(client, user, coordinator, intake_data):
    response = client.post("/intakes/add", intake_data)
    assert response.status_code == 204
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["coordinator@example.com"]
    assert message.subject == f"New intake: {intake_data['name']}"
    intake = Intake.objects.filter(name=intake_data["name"]).latest("pk")
    assert f"http://testserver/intakes/{intake.pk}/" in message.body
    assert f"{user.full_name} added a new intake." in message.body


def test_creator_is_not_emailed_about_their_own_intake(coordinator, intake_data):
    client = Client()
    client.force_login(coordinator)
    client.get("/dash/")
    client.post("/intakes/add", intake_data)
    assert Intake.objects.filter(name=intake_data["name"]).exists()
    assert mail.outbox == []


def test_only_opted_in_users_with_intake_access_are_emailed(intake):
    make_user("on")
    make_user("off", notify_new_intakes=False)
    make_user("no-access", perm_intakes=False)
    make_user("inactive", is_active=False)
    make_user("no-email", email="")
    assert notify_new_intake(intake) == 1
    assert [m.to for m in mail.outbox] == [["on@example.com"]]


def test_a_failed_send_is_swallowed(intake, coordinator, monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("apps.intakes.notify.send_mail", refuse)
    assert notify_new_intake(intake) == 0


def test_toggle_on_the_notifications_page(client, user):
    page = client.get("/settings/notifications/")
    assert "New Intake Emails" in page.content.decode()
    client.post("/settings/notifications/toggle-new-intakes/")
    user.refresh_from_db()
    assert user.notify_new_intakes
    client.post("/settings/notifications/toggle-new-intakes/")
    user.refresh_from_db()
    assert not user.notify_new_intakes


def test_toggle_is_refused_without_intake_access(client, user):
    user.perm_intakes = False
    user.save()
    page = client.get("/settings/notifications/")
    assert "New Intake Emails" not in page.content.decode()
    # Refusals redirect to the dash rather than answering 403
    response = client.post("/settings/notifications/toggle-new-intakes/")
    assert response.status_code != 200
    user.refresh_from_db()
    assert not user.notify_new_intakes
