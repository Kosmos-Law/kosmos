"""Secrets kept in the database, sealed with a key derived from SECRET_KEY.

A stored API key or OAuth token is sealed under a purpose string, so two
features never read each other's secrets and a leaked table is noise.
Rotating SECRET_KEY makes every sealed value unreadable: the feature that
owns it asks for it again (an AI key is re-entered, QuickBooks is
reconnected).
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet(purpose):
    digest = hashlib.sha256(f"{purpose}:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(value, purpose):
    """``value`` sealed for ``purpose``; blank stays blank."""
    return _fernet(purpose).encrypt(value.encode()).decode() if value else ""


def unseal(token, purpose):
    """The value sealed in ``token``: blank for a blank token, None when it
    cannot be read (SECRET_KEY changed, or the row was tampered with)."""
    if not token:
        return ""
    try:
        return _fernet(purpose).decrypt(token.encode()).decode()
    except InvalidToken:
        return None
