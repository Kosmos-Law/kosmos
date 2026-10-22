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
    case_file_enabled, library_enabled: the case builder's features, as the
    firm's administrator set them (Settings > Features).
    """

    def _ai():
        from apps.settings.ai import ai_enabled

        return ai_enabled()

    def _caselaw():
        from apps.settings.courtlistener import caselaw_available

        return caselaw_available(getattr(request, "user", None))

    def _case_file():
        from apps.settings.features import case_file_enabled

        return case_file_enabled()

    def _library():
        from apps.settings.features import library_enabled

        return library_enabled()

    def _books():
        from apps.settings.features import books_enabled

        return books_enabled()

    return {
        "ai_enabled": SimpleLazyObject(_ai),
        "caselaw_available": SimpleLazyObject(_caselaw),
        # The firm's feature switches (apps/settings/features.py).
        "case_file_enabled": SimpleLazyObject(_case_file),
        "library_enabled": SimpleLazyObject(_library),
        "books_enabled": SimpleLazyObject(_books),
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
