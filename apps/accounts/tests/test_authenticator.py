"""The authenticator app: enrolment under Settings > Security, the sign-in
step that replaces the emailed code, the firm-wide requirement, and the
resets for a lost phone."""

import re
from datetime import timedelta
from io import StringIO

import pyotp
import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from apps.accounts import totp
from apps.accounts.models import FREE_FAILURES, Authenticator, SignInThrottle
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db

User = get_user_model()
PASSWORD = "correct horse battery staple"


@pytest.fixture
def user():
    return User.objects.create_user(
        username="alice", email="alice@example.com", password=PASSWORD
    )


@pytest.fixture
def admin():
    return User.objects.create_user(
        username="boss", email="boss@example.com", password=PASSWORD, role="ADMIN"
    )


@pytest.fixture
def firm():
    return Firm.objects.create(name="Test Firm")


def _enrolled(user):
    secret = totp.new_secret()
    totp.enrol(user, secret)
    return pyotp.TOTP(secret)


def _signed_in(user):
    client = Client()
    client.force_login(user)
    client.get("/dash/")
    return client


def _code_at(app, offset):
    """The app's code ``offset`` steps from now."""
    return app.at(timezone.now() + timedelta(seconds=30 * offset))


# ---------------------------------------------------------------------------
# Enrolment
# ---------------------------------------------------------------------------


def test_setting_up_shows_a_secret_and_saves_it_once_a_code_is_confirmed(user):
    client = _signed_in(user)

    response = client.post("/settings/security/authenticator/setup/")
    assert response.status_code == 200
    assert b"<svg" in response.content
    # Nothing is saved yet: the secret waits in the session.
    assert not Authenticator.objects.filter(user=user).exists()
    secret = client.session["authenticator_setup_secret"]
    assert secret.encode() in re.sub(rb"</?span>", b"", response.content)

    response = client.post(
        "/settings/security/authenticator/confirm/",
        {"code": pyotp.TOTP(secret).now()},
    )

    assert response.status_code == 200
    assert "HX-Toast" in response
    row = Authenticator.objects.get(user=user)
    assert totp.decrypt_secret(row.secret) == secret
    assert "authenticator_setup_secret" not in client.session


def test_a_wrong_code_does_not_enrol(user):
    client = _signed_in(user)
    client.post("/settings/security/authenticator/setup/")

    response = client.post(
        "/settings/security/authenticator/confirm/", {"code": "000000"}
    )

    assert b"not right" in response.content
    assert not Authenticator.objects.filter(user=user).exists()
    # The same secret is still offered, so the app need not be set up twice.
    assert "authenticator_setup_secret" in client.session


def test_cancelling_drops_the_pending_secret(user):
    client = _signed_in(user)
    client.post("/settings/security/authenticator/setup/")

    client.get("/settings/security/authenticator/")

    assert "authenticator_setup_secret" not in client.session


def test_the_secret_is_stored_encrypted(user):
    secret = totp.new_secret()
    totp.enrol(user, secret)

    assert secret not in Authenticator.objects.get(user=user).secret


def test_turning_off_takes_a_current_code(user):
    app = _enrolled(user)
    client = _signed_in(user)

    response = client.post(
        "/settings/security/authenticator/disable/", {"code": "000000"}
    )
    assert b"not right" in response.content
    assert Authenticator.objects.filter(user=user).exists()

    client.post("/settings/security/authenticator/disable/", {"code": app.now()})
    assert not Authenticator.objects.filter(user=user).exists()


def test_turning_off_is_refused_when_the_firm_requires_the_app(user, firm):
    firm.require_authenticator = True
    firm.save()
    app = _enrolled(user)
    client = _signed_in(user)

    response = client.post(
        "/settings/security/authenticator/disable/", {"code": app.now()}
    )

    assert response.status_code == 403
    assert Authenticator.objects.filter(user=user).exists()


# ---------------------------------------------------------------------------
# Signing in
# ---------------------------------------------------------------------------


def _pass_password(client, user):
    response = client.post(
        "/accounts/login/", {"email": user.email, "password": PASSWORD}
    )
    assert response.status_code == 302
    return response


def test_an_enrolled_user_is_asked_for_the_app_code_not_an_email(user):
    app = _enrolled(user)
    client = Client()

    response = _pass_password(client, user)

    assert response["Location"] == "/accounts/login/authenticator/"
    assert mail.outbox == []
    assert "_auth_user_id" not in client.session

    response = client.post("/accounts/login/authenticator/", {"code": app.now()})

    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


def test_the_emailed_code_step_is_closed_to_an_enrolled_user(user):
    """The app is only stronger than the inbox if the inbox is not a way
    round it."""
    _enrolled(user)
    client = Client()
    _pass_password(client, user)

    response = client.post("/accounts/login/verify/", {"code": "123456"})

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_a_code_within_a_step_of_clock_drift_is_accepted(user):
    app = _enrolled(user)
    client = Client()
    _pass_password(client, user)

    client.post("/accounts/login/authenticator/", {"code": _code_at(app, -1)})

    assert client.session["_auth_user_id"] == str(user.pk)


def test_a_code_is_good_once(user):
    app = _enrolled(user)
    code = _code_at(app, 1)
    first, second = Client(), Client()
    _pass_password(first, user)
    _pass_password(second, user)

    first.post("/accounts/login/authenticator/", {"code": code})
    assert first.session["_auth_user_id"] == str(user.pk)

    response = second.post("/accounts/login/authenticator/", {"code": code})
    assert b"not right" in response.content
    assert "_auth_user_id" not in second.session


def test_the_enrolment_code_cannot_also_sign_in(user):
    client = _signed_in(user)
    client.post("/settings/security/authenticator/setup/")
    secret = client.session["authenticator_setup_secret"]
    code = pyotp.TOTP(secret).now()
    client.post("/settings/security/authenticator/confirm/", {"code": code})

    other = Client()
    _pass_password(other, user)
    other.post("/accounts/login/authenticator/", {"code": code})

    assert "_auth_user_id" not in other.session


def test_wrong_app_codes_count_toward_the_cooldown(user):
    _enrolled(user)
    client = Client()
    _pass_password(client, user)

    for _ in range(FREE_FAILURES):
        response = client.post("/accounts/login/authenticator/", {"code": "000000"})

    assert b"Too many failed sign-ins" in response.content
    assert SignInThrottle.locked_until(user.email) is not None


def test_the_app_step_needs_the_password_step_first(user):
    _enrolled(user)
    response = Client().get("/accounts/login/authenticator/")

    assert response["Location"] == "/accounts/login/"


def test_an_unreadable_secret_counts_as_no_authenticator(user, settings):
    """SECRET_KEY rotated: the row cannot be read, so the user gets the
    emailed code and sets the app up again."""
    _enrolled(user)
    settings.SECRET_KEY = "another key entirely"
    client = Client()

    response = _pass_password(client, user)

    assert response["Location"] == "/accounts/login/verify/"
    assert len(mail.outbox) == 1


# ---------------------------------------------------------------------------
# The firm-wide requirement
# ---------------------------------------------------------------------------


def test_a_required_user_without_an_app_can_only_reach_security(user, firm):
    firm.require_authenticator = True
    firm.save()
    client = _signed_in(user)

    response = client.get("/matters/")
    assert response.status_code == 302
    assert response["Location"] == "/settings/security/"

    response = client.get("/matters/", HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert response["HX-Redirect"] == "/settings/security/"

    assert client.get("/settings/security/").status_code == 200
    assert client.post("/settings/security/authenticator/setup/").status_code == 200
    assert client.post("/accounts/logout/").status_code == 302


def test_an_enrolled_user_is_not_redirected(user, firm):
    firm.require_authenticator = True
    firm.save()
    _enrolled(user)
    client = _signed_in(user)

    assert client.get("/matters/").status_code == 200


def test_nobody_is_redirected_while_the_firm_does_not_require_it(user, firm):
    client = _signed_in(user)

    assert client.get("/matters/").status_code == 200


def test_the_firm_page_saves_the_requirement(admin, firm):
    client = _signed_in(admin)

    client.post(
        "/settings/firm/",
        {"name": "Test Firm", "require_authenticator": "True"},
    )

    firm.refresh_from_db()
    assert firm.require_authenticator is True


# ---------------------------------------------------------------------------
# Resets for a lost phone
# ---------------------------------------------------------------------------


def test_an_administrator_resets_a_users_app(user, admin):
    _enrolled(user)
    client = _signed_in(admin)

    response = client.post(f"/settings/users/reset-authenticator/{user.pk}/")

    assert response.status_code == 204
    assert not Authenticator.objects.filter(user=user).exists()


def test_a_user_cannot_reset_anothers_app(user, admin):
    _enrolled(admin)
    client = _signed_in(user)

    response = client.post(f"/settings/users/reset-authenticator/{admin.pk}/")

    assert response.status_code == 403
    assert Authenticator.objects.filter(user=admin).exists()


def test_the_command_resets_by_email(user):
    _enrolled(user)
    out = StringIO()

    call_command("reset_authenticator", "ALICE@example.com", stdout=out)

    assert not Authenticator.objects.filter(user=user).exists()
    assert "reset" in out.getvalue()


def test_the_app_is_told_the_firms_name(user, firm, settings):
    settings.ENV = "prod"
    uri = totp.provisioning_uri("ABCDEFGHIJKLMNOP", user)

    assert "issuer=Kosmos%20%28Test%20Firm%29" in uri
    assert uri.startswith(
        "otpauth://totp/Kosmos%20%28Test%20Firm%29:alice%40example.com?"
    )


def test_without_a_firm_name_the_app_is_told_kosmos(user, settings):
    settings.ENV = "prod"
    assert totp.issuer() == "Kosmos"


def test_the_development_site_says_dev_instead_of_the_firm(firm, settings):
    settings.ENV = "dev"

    assert totp.issuer() == "Kosmos (dev)"
