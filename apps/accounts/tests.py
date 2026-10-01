from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.utils import timezone

from apps.accounts.models import EmailVerificationCode
from apps.accounts.views import MAX_CODE_ATTEMPTS

pytestmark = pytest.mark.django_db

User = get_user_model()
PASSWORD = "correct horse battery staple"


@pytest.fixture
def user():
    return User.objects.create_user(
        username="alice", email="alice@example.com", password=PASSWORD
    )


@pytest.fixture
def staff_user():
    return User.objects.create_superuser(
        username="root", email="root@example.com", password=PASSWORD
    )


def _pass_step_one(client, user, **extra):
    response = client.post(
        "/accounts/login/", {"username": user.username, "password": PASSWORD, **extra}
    )
    assert response.status_code == 302
    return EmailVerificationCode.objects.get(user=user)


def _wrong_code(verification):
    return "000000" if verification.code != "000000" else "111111"


def test_password_then_emailed_code_signs_in(user):
    client = Client()
    verification = _pass_step_one(client, user)

    assert len(mail.outbox) == 1
    assert verification.code in mail.outbox[0].body
    # The password alone has not signed anyone in.
    assert "_auth_user_id" not in client.session

    response = client.post("/accounts/login/verify/", {"code": verification.code})

    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


def test_admin_login_form_is_replaced_by_the_emailed_code_sign_in(staff_user):
    client = Client()

    response = client.get("/admin/login/?next=/admin/")
    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/")

    # Posting a staff password straight at the admin form signs nobody in.
    response = client.post(
        "/admin/login/", {"username": staff_user.username, "password": PASSWORD}
    )
    assert "_auth_user_id" not in client.session


def test_unauthenticated_admin_request_ends_at_the_code_sign_in():
    response = Client().get("/admin/", follow=True)

    assert response.redirect_chain[-1][0].startswith("/accounts/login/")


def test_code_is_discarded_after_too_many_wrong_attempts(user):
    client = Client()
    verification = _pass_step_one(client, user)
    wrong = _wrong_code(verification)

    for _ in range(MAX_CODE_ATTEMPTS):
        client.post("/accounts/login/verify/", {"code": wrong})

    assert not EmailVerificationCode.objects.filter(user=user).exists()
    # Even the right code is now useless: step one has to be repeated.
    response = client.post("/accounts/login/verify/", {"code": verification.code})
    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/"
    assert "_auth_user_id" not in client.session


def test_a_few_wrong_attempts_do_not_lock_out_the_right_code(user):
    client = Client()
    verification = _pass_step_one(client, user)

    for _ in range(MAX_CODE_ATTEMPTS - 1):
        client.post("/accounts/login/verify/", {"code": _wrong_code(verification)})
    client.post("/accounts/login/verify/", {"code": verification.code})

    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.parametrize("age", [timedelta(minutes=6), timedelta(days=1, minutes=1)])
def test_code_expires_and_stays_expired(user, age):
    verification = EmailVerificationCode.objects.create(user=user, code="123456")
    EmailVerificationCode.objects.filter(pk=verification.pk).update(
        created_at=timezone.now() - age
    )
    verification.refresh_from_db()

    assert verification.is_expired()


def test_next_url_on_this_site_is_followed(user):
    client = Client()
    verification = _pass_step_one(client, user, next="/matters/")

    response = client.post("/accounts/login/verify/", {"code": verification.code})

    assert response["Location"] == "/matters/"


@pytest.mark.parametrize("target", ["https://evil.example.com/", "//evil.example.com/"])
def test_next_url_to_another_site_is_ignored(user, target):
    client = Client()
    verification = _pass_step_one(client, user, next=target)

    response = client.post("/accounts/login/verify/", {"code": verification.code})

    assert "evil.example.com" not in response["Location"]
