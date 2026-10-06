import os

from django.conf import settings
from django.utils.functional import SimpleLazyObject

from utils.mail import email_delivers


def env(request):
    return {
        "env": os.environ.get("ENV"),
        # base.html shows admins a banner when mail goes to the server log
        # instead of out (console mode). A development machine (DEBUG on)
        # expects that, so it stays quiet there.
        "email_not_delivering": not settings.DEBUG and not email_delivers(),
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


def payments(request):
    """Whether online payment is on, for the templates that offer it.

    `payment_requests_exist` is a callable, so its query only runs where a
    template asks (the Invoicing sub-nav, and only while payments are off).
    """
    from apps.invoicing.processors import online_payments_enabled
    from apps.invoicing.requests.models import PaymentRequest

    return {
        "online_payments_enabled": online_payments_enabled(),
        "payment_requests_exist": PaymentRequest.objects.exists,
    }
