"""The quick payment form answers 404 to an invoice that does not exist, and
to nothing else: any other failure is an error, not a missing page."""

from unittest.mock import patch

import pytest
from django.db.models.query import QuerySet
from django.urls import reverse

from apps.invoicing.invoices.models import Invoice

pytestmark = pytest.mark.django_db


def _url(pk):
    return reverse(
        "invoicing:quick-invoice-payment", kwargs={"pk": pk, "payment_type": "check"}
    )


def test_missing_invoice_is_404(client):
    assert client.get(_url(999999)).status_code == 404


def test_other_failures_are_not_404(client, invoice):
    real_get = QuerySet.get

    def get(queryset, *args, **kwargs):
        if queryset.model is Invoice:
            raise RuntimeError("database away")
        return real_get(queryset, *args, **kwargs)

    with patch.object(QuerySet, "get", get):
        with pytest.raises(RuntimeError, match="database away"):
            client.get(_url(invoice.pk))
