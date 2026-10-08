"""The sidebar's account menu (who is signed in, Settings, Log out), Sign
Out Everywhere on the Security page, and the icon that stands for the
user."""

import re

import pytest
from django.contrib.auth.base_user import AbstractBaseUser
from django.test import Client
from django.urls import reverse

from apps.accounts.models import NAV_ICONS, CustomUser

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return CustomUser.objects.create_user(
        username="james",
        email="james@example.com",
        password="pw",
        first_name="James",
        last_name="Craig",
    )


def signed_in_client(user):
    client = Client()
    client.force_login(user)
    client.get("/dash/")
    return client


def test_the_menu_shows_who_is_signed_in_and_logs_out(user):
    html = signed_in_client(user).get(reverse("tasks:index")).content.decode()

    assert "James Craig" in html
    assert "james@example.com" in html
    assert f'action="{reverse("accounts:logout")}"' in html
    assert ">Settings</a>" not in html.split('class="account-menu')[0]


def test_log_out_signs_out(user):
    client = signed_in_client(user)

    client.post(reverse("accounts:logout"))

    assert "_auth_user_id" not in client.session


def test_settings_opens_on_profile_and_the_session_page_is_gone(user):
    client = signed_in_client(user)

    response = client.get(reverse("settings:settings"))
    assert response.status_code == 302
    assert response["Location"] == reverse("settings:profile-index")
    assert client.get("/settings/session/").status_code == 404


def test_before_any_sign_out_the_hash_is_djangos(user):
    # Adding the count signed no one out.
    assert user.get_session_auth_hash() == AbstractBaseUser.get_session_auth_hash(user)


def test_sign_out_everywhere_ends_the_others_and_keeps_this_one(user):
    here = signed_in_client(user)
    phone = signed_in_client(user)

    response = here.post(reverse("settings:sign-out-everywhere"))

    assert b"Every other session is signed out" in response.content
    assert here.get(reverse("tasks:index")).status_code == 200
    assert phone.get(reverse("tasks:index")).status_code == 302


def test_sign_out_everywhere_twice_still_keeps_this_one(user):
    here = signed_in_client(user)

    here.post(reverse("settings:sign-out-everywhere"))
    here.post(reverse("settings:sign-out-everywhere"))

    assert here.get(reverse("tasks:index")).status_code == 200


def test_the_person_is_the_icon_until_another_is_chosen(user):
    html = signed_in_client(user).get(reverse("tasks:index")).content.decode()

    assert re.search(r'class="account-button"[^>]*>\s*<i class="icon-user">', html)


def test_a_chosen_icon_stands_in_the_sidebar(user):
    client = signed_in_client(user)

    response = client.post(reverse("settings:nav-icon"), {"icon": "chess-knight"})

    assert response["Location"] == reverse("settings:profile-index")
    user.refresh_from_db()
    assert user.nav_icon == "chess-knight"
    html = client.get(reverse("tasks:index")).content.decode()
    assert re.search(
        r'class="account-button"[^>]*>\s*<i class="icon-chess-knight">', html
    )


def test_an_icon_not_in_the_set_is_ignored(user):
    client = signed_in_client(user)

    client.post(reverse("settings:nav-icon"), {"icon": 'x" onmouseover="alert(1)'})

    user.refresh_from_db()
    assert user.nav_icon == "user"


def test_the_profile_offers_every_icon_and_marks_the_chosen(user):
    html = signed_in_client(user).get(reverse("settings:profile-index")).content

    for name, _ in NAV_ICONS:
        assert f'<i class="icon-{name}"></i>'.encode() in html
    assert re.search(rb'value="user"\s+class="icon-choice chosen"', html)
