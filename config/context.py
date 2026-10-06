import os


def env(request):
    return {
        "env": os.environ.get("ENV"),
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
