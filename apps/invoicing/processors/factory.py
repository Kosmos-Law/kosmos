"""Select the active payment processor from settings.

    PAYMENT_PROCESSOR = "fake"   # or "none", "lawpay", "stripe", "confido"

The default is "fake" so development and the test suite run without any
processor credentials. "fake" records payments although no money moves, so a
production install that takes no online payments should set "none".
"""

from django.conf import settings

from .base import PaymentProcessor, ProcessorConfigError
from .fake import FakeProcessor


def online_payments_enabled() -> bool:
    """Whether clients can pay online at all.

    False only for "none", which switches online payment off: nothing should
    then offer or promise it (no Pay now link in emails, no payment or trust
    deposit requests). Every other value, "fake" included, counts as on, so a
    misconfigured real processor still shows its own error rather than
    silently hiding the feature.
    """
    return getattr(settings, "PAYMENT_PROCESSOR", "fake") != "none"


def get_processor(name: str | None = None) -> PaymentProcessor:
    """Return an instance of the configured (or named) processor."""
    name = name or getattr(settings, "PAYMENT_PROCESSOR", "fake")

    if name == "fake":
        return FakeProcessor()

    if name == "none":
        from .none import DisabledProcessor

        return DisabledProcessor()

    if name == "lawpay":
        # Imported lazily so the package needn't import `requests` unless the
        # LawPay processor is actually selected.
        from .lawpay import LawPayProcessor

        return LawPayProcessor()

    if name == "stripe":
        # Imported lazily so the package needn't import `stripe` unless selected.
        from .stripe import StripeProcessor

        return StripeProcessor()

    if name == "confido":
        # Imported lazily so the package needn't import `requests` unless the
        # Confido processor is actually selected.
        from .confido import ConfidoProcessor

        return ConfidoProcessor()

    raise ProcessorConfigError(f"Unknown PAYMENT_PROCESSOR: {name!r}")
