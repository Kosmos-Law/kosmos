"""Online payments switched off (``PAYMENT_PROCESSOR=none``).

For a firm that collects no money through Kosmos. The emailed links still
work, because they are also how a client downloads the invoice or statement:
the page shows the amount due and the documents, and tells the client to
contact the firm instead of offering a payment form. Nothing can be charged or
recorded.

This is what a production install should run until a real processor is
configured. ``fake`` is for development: it records a payment although no
money moved.
"""

from .base import (
    ChargeError,
    ChargeResult,
    ClientConfig,
    PaymentProcessor,
    ProcessorConfigError,
    WebhookEvent,
    WebhookVerificationError,
)

MESSAGE = "Online payment is not available."


class DisabledProcessor(PaymentProcessor):
    name = "none"

    def client_config(self, invoice) -> ClientConfig:
        amount_cents = int(round(float(invoice.amount_remaining) * 100))
        return self.client_config_for(
            amount_cents=amount_cents, reference=f"Invoice {invoice.id}"
        )

    def client_config_for(
        self, *, amount_cents, reference, trust=False
    ) -> ClientConfig:
        return ClientConfig(
            processor=self.name,
            public_key="",
            amount_cents=amount_cents,
            reference=reference,
            methods=[],
        )

    def trust_unavailable_reason(self) -> str:
        return "online payments are not set up."

    def charge(self, **kwargs) -> ChargeResult:
        raise ChargeError(MESSAGE, code="disabled")

    def fetch_transaction(self, transaction_id: str) -> ChargeResult:
        raise ProcessorConfigError(MESSAGE)

    def verify_and_parse_webhook(self, request) -> WebhookEvent:
        raise WebhookVerificationError(MESSAGE)

    def refund(self, **kwargs) -> ChargeResult:
        raise ProcessorConfigError(MESSAGE)
