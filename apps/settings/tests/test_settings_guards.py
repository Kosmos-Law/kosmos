"""Settings actions that could lock the firm out, be triggered by a link,
or connect an account the session never asked for."""

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.mail.models import GmailAccount
from apps.matters.models import PracticeArea, Role

pytestmark = pytest.mark.django_db


def _admin():
    return CustomUser.objects.get(role="ADMIN")


# --- the last administrator ---------------------------------------------------


def test_the_only_admin_cannot_be_demoted(admin_client):
    admin = _admin()

    response = admin_client.post(
        reverse("settings:change-role", args=[admin.id, "USER"])
    )

    assert response.status_code == 204
    assert "only active administrator" in response.headers["HX-Toast"]
    admin.refresh_from_db()
    assert admin.role == "ADMIN"


def test_the_only_admin_cannot_be_deactivated(admin_client):
    admin = _admin()

    response = admin_client.post(reverse("settings:switch-status", args=[admin.id]))

    assert "only active administrator" in response.headers["HX-Toast"]
    admin.refresh_from_db()
    assert admin.is_active


def test_an_admin_can_be_demoted_when_another_remains(admin_client):
    admin = _admin()
    other = CustomUser.objects.create(username="Second", role="ADMIN")

    admin_client.post(reverse("settings:change-role", args=[other.id, "USER"]))

    other.refresh_from_db()
    assert other.role == "USER"
    assert _admin() == admin


# --- deletes and disconnects need a POST ---------------------------------------


def test_a_link_cannot_delete_a_practice_area_or_a_role(admin_client):
    area = PracticeArea.objects.create(name="Zoning Appeals", is_active=True)
    role = Role.objects.create(name="Expert Zed")

    assert (
        admin_client.get(
            reverse("settings:delete-practice-area", args=[area.id])
        ).status_code
        == 405
    )
    assert (
        admin_client.get(reverse("settings:delete-role", args=[role.id])).status_code
        == 405
    )
    assert PracticeArea.objects.filter(pk=area.pk).exists()
    assert Role.objects.filter(pk=role.pk).exists()


def test_a_link_cannot_disconnect_a_mailbox(client, user):
    GmailAccount.objects.create(user=user, address="me@example.com", token="{}")

    assert (
        client.get(reverse("settings:google-logout", args=["email"])).status_code == 405
    )
    assert GmailAccount.objects.filter(user=user).exists()

    assert (
        client.post(reverse("settings:google-logout", args=["email"])).status_code
        == 302
    )
    assert not GmailAccount.objects.filter(user=user).exists()


# --- connecting Google ----------------------------------------------------------


def test_a_google_callback_this_session_did_not_start_is_refused(admin_client):
    response = admin_client.get(
        reverse("settings:google-store"), {"state": "someone-elses", "code": "abc"}
    )

    assert response.status_code == 400


def test_a_google_callback_with_the_wrong_state_is_refused(admin_client):
    session = admin_client.session
    session["state"] = "expected"
    session["app"] = "calendar"
    session.save()

    response = admin_client.get(
        reverse("settings:google-store"), {"state": "forged", "code": "abc"}
    )

    assert response.status_code == 400
    assert "state" not in admin_client.session


# --- smaller ---------------------------------------------------------------------


def test_sorting_the_user_list_keeps_inactive_users_out(admin_client):
    CustomUser.objects.create(username="Gone", is_active=False)

    admin_client.post(reverse("settings:user-sort", args=["user_rate"]))
    response = admin_client.get(reverse("settings:user-list"))

    assert admin_client.session["user_filter"]["order_by"] == "user_rate"
    assert b"Gone" not in response.content


def test_an_invalid_profile_shows_the_form_again(client, user):
    CustomUser.objects.create(username="Taken")

    response = client.post(
        reverse("settings:personal-profile", args=["profile"]),
        {"username": "Taken", "email": "not-an-email"},
    )

    assert response.status_code == 200


def test_a_user_sees_only_their_own_mailbox_health(client, user):
    colleague = CustomUser.objects.create(username="Colleague")
    GmailAccount.objects.create(user=user, address="me@example.com", token="{}")
    GmailAccount.objects.create(user=colleague, address="them@example.com", token="{}")

    body = client.get(reverse("settings:integrations-index")).content.decode()

    assert "me@example.com" in body
    assert "them@example.com" not in body
