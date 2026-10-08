"""Authenticator-app codes (TOTP) for the second sign-in step.

The secret is kept encrypted with a key derived from SECRET_KEY, as the AI
provider keys are (apps/settings/ai.py). Rotating SECRET_KEY therefore
makes every stored authenticator unreadable; such a row counts as no
authenticator, and the user sets the app up again.
"""

import base64
import hashlib
import hmac
import logging

import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils import timezone

from .models import Authenticator

logger = logging.getLogger(__name__)

ISSUER = "Kosmos"
# Steps either side of now that a code is accepted for: a phone's clock up
# to 30 seconds out still signs in.
DRIFT_STEPS = 1


def _fernet():
    digest = hashlib.sha256(
        f"kosmos-authenticator:{settings.SECRET_KEY}".encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(secret):
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        logger.warning(
            "A stored authenticator cannot be decrypted (SECRET_KEY changed?)"
        )
        return ""


def new_secret():
    return pyotp.random_base32()


def issuer():
    """What the app shows above the account: "Kosmos (Firm Name)", or
    plain "Kosmos" before the firm has a name. A colon cannot appear in an
    otpauth issuer, so one in the name is dropped."""
    from apps.settings.models import Firm

    firm = Firm.objects.only("name").first()
    name = (firm.name if firm else "").replace(":", "").strip()
    return f"{ISSUER} ({name})" if name else ISSUER


def provisioning_uri(secret, user):
    return pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=issuer())


def qr_svg(uri):
    """The QR code as inline SVG markup. Drawn black on white whatever the
    theme: a phone camera reads that, and not every app reads an inverted
    code."""
    return segno.make(uri, error="m").svg_inline(
        scale=5, border=2, dark="#000", light="#fff"
    )


def usable_authenticator(user):
    """The user's authenticator with its secret readable, else None."""
    row = Authenticator.objects.filter(user_id=user.pk).first()
    if row is None:
        return None
    secret = decrypt_secret(row.secret)
    if not secret:
        return None
    row.plain_secret = secret
    return row


def _matching_counter(secret, code, after=0):
    """The time step whose code is ``code``, within the drift window and
    later than ``after``; None when no step matches."""
    totp = pyotp.TOTP(secret)
    now = totp.timecode(timezone.now())
    for offset in range(-DRIFT_STEPS, DRIFT_STEPS + 1):
        counter = now + offset
        if counter > after and hmac.compare_digest(totp.generate_otp(counter), code):
            return counter
    return None


def matching_counter(secret, code):
    """For enrolment: the step whose code the app shows for a secret not
    yet saved, or None when ``code`` is not it."""
    return _matching_counter(secret, code)


def verify(authenticator, code):
    """True when ``code`` is the app's current code and has not been used.
    The accepted step is recorded so the same code cannot sign in twice."""
    counter = _matching_counter(
        authenticator.plain_secret, code, after=authenticator.last_counter
    )
    if counter is None:
        return False
    Authenticator.objects.filter(pk=authenticator.pk).update(last_counter=counter)
    return True


def enrol(user, secret, spent_counter=0):
    """Save ``secret`` as the user's authenticator, replacing any earlier
    one. ``spent_counter`` is the step of the code that confirmed the
    setup, recorded so that code cannot be the first sign-in code too."""
    Authenticator.objects.update_or_create(
        user=user,
        defaults={"secret": encrypt_secret(secret), "last_counter": spent_counter},
    )
