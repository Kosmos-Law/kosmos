"""Whether AI is set up on this server, and with which providers.

AI is optional. A provider is configured when its API key is set in
config/.env (GEMINI_API_KEY, ANTHROPIC_API_KEY) or entered by an admin
under Settings > Integrations; the .env value wins. With neither key every
AI surface is hidden and no AI work is queued.

Keys entered in Settings are stored encrypted with a key derived from
SECRET_KEY, so rotating SECRET_KEY makes them unreadable: re-enter them.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

GEMINI = "gemini"
ANTHROPIC = "anthropic"

PROVIDER_LABELS = {GEMINI: "Google Gemini", ANTHROPIC: "Anthropic Claude"}

_ENV_SETTINGS = {GEMINI: "GEMINI_API_KEY", ANTHROPIC: "ANTHROPIC_API_KEY"}
_FIRM_FIELDS = {GEMINI: "gemini_api_key", ANTHROPIC: "anthropic_api_key"}


def _fernet():
    digest = hashlib.sha256(f"kosmos-ai-keys:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_key(value):
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt_key(token):
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        logger.warning("A stored AI key cannot be decrypted (SECRET_KEY changed?)")
        return ""


def _firm():
    from apps.settings.models import Firm

    return Firm.objects.first()


def env_key(provider):
    return getattr(settings, _ENV_SETTINGS[provider], "") or ""


def stored_key(provider, firm=None):
    firm = firm if firm is not None else _firm()
    return decrypt_key(getattr(firm, _FIRM_FIELDS[provider], "")) if firm else ""


def api_key(provider):
    """The key to call ``provider`` with: .env first, then Settings."""
    return env_key(provider) or stored_key(provider)


def key_source(provider, firm=None):
    """Where the key comes from, for the Settings page: "env",
    "settings" or None."""
    if env_key(provider):
        return "env"
    if stored_key(provider, firm):
        return "settings"
    return None


def gemini_key():
    return api_key(GEMINI)


def anthropic_key():
    return api_key(ANTHROPIC)


def configured_providers():
    """Providers with a key, Gemini first (the cheaper default for
    background work). One Firm read at most."""
    providers = [p for p in (GEMINI, ANTHROPIC) if env_key(p)]
    if len(providers) < 2:
        firm = _firm()
        providers += [
            p for p in (GEMINI, ANTHROPIC) if p not in providers and stored_key(p, firm)
        ]
    return sorted(providers, key=(GEMINI, ANTHROPIC).index)


def ai_enabled():
    """True when at least one provider has a key."""
    return bool(configured_providers())
