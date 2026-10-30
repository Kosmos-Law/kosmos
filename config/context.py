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
    case_file_enabled: the case builder's feature, as the firm's
    administrator set it (Settings > Features).
    """

    def _ai():
        from apps.settings.ai import ai_enabled

        return ai_enabled()

    def _case_file():
        from apps.settings.features import case_file_enabled

        return case_file_enabled()

    def _accounting():
        from apps.settings.features import accounting_enabled

        return accounting_enabled()

    def _accounting_mirror():
        # The QuickBooks connection while Accounting mirrors it (apps/accounting/sync.py),
        # or None. Read only by the Accounting pages and the Integrations page.
        from apps.accounting import intuit

        return intuit.connection()

    return {
        "ai_enabled": SimpleLazyObject(_ai),
        # The firm's feature switches (apps/settings/features.py).
        "case_file_enabled": SimpleLazyObject(_case_file),
        "accounting_enabled": SimpleLazyObject(_accounting),
        "accounting_mirror": SimpleLazyObject(_accounting_mirror),
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
