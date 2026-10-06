import os

from django.utils.functional import SimpleLazyObject


def env(request):
    return {
        "env": os.environ.get("ENV"),
    }


def integrations(request):
    """Which optional integrations this page may show, computed only when
    a template asks.

    ai_enabled: an AI provider key is set (apps/settings/ai.py).
    caselaw_available: a CourtListener token is set and the user holds the
    Research permission; saved case law is a view of the AI tab, or its
    own tab when AI is off.
    """

    def _ai():
        from apps.settings.ai import ai_enabled

        return ai_enabled()

    def _caselaw():
        from apps.case.courtlistener import caselaw_available

        return caselaw_available(getattr(request, "user", None))

    return {
        "ai_enabled": SimpleLazyObject(_ai),
        "caselaw_available": SimpleLazyObject(_caselaw),
    }
