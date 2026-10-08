"""The invoicing models live in sub-packages. Importing them here registers
them with the app registry as the app loads; nothing else does at start-up
since the admin was removed, and a relation into this app from another
(trust's Transaction.payment) cannot resolve until they are."""

from apps.invoicing.applications.models import (  # noqa: F401
    CreditApplication,
    PaymentApplication,
)
from apps.invoicing.credits.models import Credit  # noqa: F401
from apps.invoicing.invoices.models import Invoice  # noqa: F401
from apps.invoicing.payments.models import Payment  # noqa: F401
from apps.invoicing.requests.models import PaymentRequest  # noqa: F401
