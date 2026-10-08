"""Authenticator-app codes (TOTP, RFC 6238) for the second sign-in step.

The codes are the six digits every authenticator app shows, from a secret
the app and the site share, changing every 30 seconds. A code is taken
from one step either side of now, for clocks that have drifted, and never
twice: the step of the last code taken is kept, and only a later one is
accepted.

The secret is stored as it is, like the password hashes and the emailed
codes beside it. It is not encrypted with a key kept on the same server:
that would protect it only in a database copy taken without the server's
config, and would tie every enrolment to SECRET_KEY, so that rotating the
key, or restoring the database on a machine with another key, signed the
whole firm out of their apps. cpl made the same choice.
"""

import hmac

import pyotp
import segno
from django.conf import settings
from django.utils import timezone

from .models import Authenticator

ISSUER = "Kosmos"
# Steps either side of now that a code is accepted for: a phone's clock up
# to 30 seconds out still signs in.
DRIFT_STEPS = 1


def new_secret():
    return pyotp.random_base32()


def issuer():
    """What the app shows above the account: "Kosmos (Firm Name)", or
    plain "Kosmos" before the firm has a name. On the development site
    (ENV=dev) it is "Kosmos (dev)" instead, so the two sites' accounts are
    told apart in the app. A colon cannot appear in an otpauth issuer, so
    one in the name is dropped."""
    from apps.settings.models import Firm

    if settings.ENV == "dev":
        return f"{ISSUER} (dev)"
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


def authenticator_for(user):
    """The user's authenticator row, or None."""
    return Authenticator.objects.filter(user_id=user.pk).first()


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
    Taking it moves the row's last step on in one guarded update, so two
    requests racing with the same code cannot both win."""
    counter = _matching_counter(
        authenticator.secret, code, after=authenticator.last_counter
    )
    if counter is None:
        return False
    taken = Authenticator.objects.filter(
        pk=authenticator.pk, last_counter__lt=counter
    ).update(last_counter=counter)
    if taken:
        authenticator.last_counter = counter
    return bool(taken)


def enrol(user, secret, spent_counter=0):
    """Save ``secret`` as the user's authenticator, replacing any earlier
    one. ``spent_counter`` is the step of the code that confirmed the
    setup, recorded so that code cannot be the first sign-in code too."""
    Authenticator.objects.update_or_create(
        user=user, defaults={"secret": secret, "last_counter": spent_counter}
    )
