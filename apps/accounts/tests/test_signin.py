from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.utils import timezone

from apps.accounts.models import (
    COOLDOWN_CAP,
    FREE_FAILURES,
    EmailVerificationCode,
    SignInThrottle,
)
from apps.accounts.views import MAX_CODE_ATTEMPTS

pytestmark = pytest.mark.django_db

User = get_user_model()
PASSWORD = "correct horse battery staple"


@pytest.fixture
def user():
    return User.objects.create_user(
        username="alice", email="alice@example.com", password=PASSWORD
    )


def _pass_step_one(client, user, **extra):
    response = client.post(
        "/accounts/login/", {"email": user.email, "password": PASSWORD, **extra}
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


def test_the_email_is_matched_whatever_its_case(user):
    client = Client()
    response = client.post(
        "/accounts/login/", {"email": "Alice@Example.COM", "password": PASSWORD}
    )

    assert response.status_code == 302
    assert EmailVerificationCode.objects.filter(user=user).exists()


def test_the_username_does_not_sign_in(user):
    client = Client()
    response = client.post("/accounts/login/", {"email": "alice", "password": PASSWORD})

    assert response.status_code == 200
    assert not EmailVerificationCode.objects.filter(user=user).exists()


def test_a_wrong_password_is_refused_without_saying_which_part(user):
    client = Client()
    response = client.post(
        "/accounts/login/", {"email": user.email, "password": "nope"}
    )

    assert response.status_code == 200
    assert b"email address or password is not right" in response.content
    assert not EmailVerificationCode.objects.filter(user=user).exists()


def test_the_sign_in_form_is_restored_on_an_error(user):
    client = Client()
    response = client.post(
        "/accounts/login/", {"email": "alice@example.com", "password": "nope"}
    )
    assert response.status_code == 200
    assert b'name="email"' in response.content
    assert b'name="password"' in response.content


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


def test_wrong_attempts_are_counted_per_code_across_sessions(user):
    """Someone holding the password can open many sessions. The guesses they
    get against the one live code must not multiply with them."""
    first, second = Client(), Client()
    _pass_step_one(first, user)
    # A second sign-in replaces the code; both sessions now wait on it.
    verification = _pass_step_one(second, user)
    wrong = _wrong_code(verification)

    for _ in range(MAX_CODE_ATTEMPTS - 1):
        first.post("/accounts/login/verify/", {"code": wrong})
    assert EmailVerificationCode.objects.filter(user=user).exists()

    # The other session's first wrong guess is the code's last.
    second.post("/accounts/login/verify/", {"code": wrong})

    assert not EmailVerificationCode.objects.filter(user=user).exists()
    for client in (first, second):
        client.post("/accounts/login/verify/", {"code": verification.code})
        assert "_auth_user_id" not in client.session


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


# ---------------------------------------------------------------------------
# The cooldown on repeated failures
# ---------------------------------------------------------------------------


def _fail(client, email, times):
    for _ in range(times):
        client.post("/accounts/login/", {"email": email, "password": "wrong"})


def test_the_first_failures_are_free_then_a_cooldown_starts(user):
    client = Client()
    _fail(client, user.email, FREE_FAILURES - 1)
    assert SignInThrottle.locked_until(user.email) is None

    _fail(client, user.email, 1)
    assert SignInThrottle.locked_until(user.email) is not None

    # The right password is not even tried during the cooldown.
    response = client.post(
        "/accounts/login/", {"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    assert b"Too many failed sign-ins" in response.content
    assert not EmailVerificationCode.objects.filter(user=user).exists()


def test_the_cooldown_grows_with_each_failure_up_to_the_cap():
    assert SignInThrottle.cooldown_for(FREE_FAILURES - 1) == timedelta(0)
    assert SignInThrottle.cooldown_for(FREE_FAILURES) == timedelta(seconds=30)
    assert SignInThrottle.cooldown_for(FREE_FAILURES + 1) == timedelta(minutes=1)
    assert SignInThrottle.cooldown_for(FREE_FAILURES + 2) == timedelta(minutes=2)
    assert SignInThrottle.cooldown_for(FREE_FAILURES + 40) == COOLDOWN_CAP


def test_the_cooldown_applies_to_addresses_that_belong_to_nobody():
    """A cooldown for real accounts alone would say which addresses exist."""
    client = Client()
    _fail(client, "nobody@example.com", FREE_FAILURES)

    response = client.post(
        "/accounts/login/", {"email": "nobody@example.com", "password": "x"}
    )
    assert b"Too many failed sign-ins" in response.content


def test_the_cooldown_is_per_address_and_case_blind(user):
    client = Client()
    _fail(client, "ALICE@example.com", FREE_FAILURES)

    assert SignInThrottle.locked_until("alice@example.com") is not None
    assert SignInThrottle.locked_until("bob@example.com") is None


def test_a_cooldown_ends_and_old_failures_are_forgotten(user):
    client = Client()
    _fail(client, user.email, FREE_FAILURES)
    row = SignInThrottle.objects.get(email=user.email)
    SignInThrottle.objects.filter(pk=row.pk).update(
        last_failure_at=timezone.now() - timedelta(hours=2)
    )

    assert SignInThrottle.locked_until(user.email) is None
    # The next failure starts the count again rather than deepening it.
    _fail(client, user.email, 1)
    assert SignInThrottle.objects.get(email=user.email).failures == 1


def test_a_completed_sign_in_clears_the_count(user):
    client = Client()
    _fail(client, user.email, FREE_FAILURES - 1)

    verification = _pass_step_one(client, user)
    # Still counted: the password alone is not the sign-in.
    assert SignInThrottle.objects.get(email=user.email).failures == FREE_FAILURES - 1

    client.post("/accounts/login/verify/", {"code": verification.code})
    assert client.session["_auth_user_id"] == str(user.pk)
    assert not SignInThrottle.objects.filter(email=user.email).exists()


def test_rows_nobody_has_tried_in_a_day_are_dropped(user):
    SignInThrottle.objects.create(
        email="stale@example.com",
        failures=2,
        last_failure_at=timezone.now() - timedelta(days=2),
    )

    SignInThrottle.record_failure(user.email)

    assert not SignInThrottle.objects.filter(email="stale@example.com").exists()
