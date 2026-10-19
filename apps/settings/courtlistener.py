"""Whether CourtListener is set up, and for whom saved case law is on. The
client itself is apps/case/courtlistener.py; this is the integration's
on/off switch, which the access middleware and the page context need
without the client."""

from django.conf import settings


def get_api_token() -> str:
    """The CourtListener API token from settings."""
    return getattr(settings, "COURTLISTENER_API_TOKEN", "")


def caselaw_available(user) -> bool:
    """Saved case law is offered when CourtListener is set up and the user
    holds the Research permission (admins hold every permission)."""
    return bool(get_api_token()) and bool(
        user and user.is_authenticated and (user.is_admin or user.perm_research)
    )
