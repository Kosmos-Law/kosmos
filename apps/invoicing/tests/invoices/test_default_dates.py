"""The date a form or dialog offers by default is today in the firm's time
zone, not the server's. Late on an evening in New York the server (UTC) is
already on tomorrow."""

from datetime import (
    date,
    datetime,
    timezone as dt_timezone,
)
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.invoicing.credits.forms import CreditsForm
from apps.invoicing.invoices.forms import InvoiceForm
from apps.invoicing.payments.forms import PaymentForm

pytestmark = pytest.mark.django_db

# 03:00 UTC on 2 January is 22:00 on 1 January in New York.
UTC_NOW = datetime(2026, 1, 2, 3, 0, tzinfo=dt_timezone.utc)
NEW_YORK_TODAY = date(2026, 1, 1)


@pytest.fixture
def new_york_evening():
    with (
        override_settings(TIME_ZONE="America/New_York"),
        patch("django.utils.timezone.now", return_value=UTC_NOW),
    ):
        yield


def test_payment_form_dates_today_in_firm_zone(new_york_evening):
    assert PaymentForm().fields["date"].initial == NEW_YORK_TODAY


def test_credit_form_dates_today_in_firm_zone(new_york_evening):
    assert CreditsForm().fields["date"].initial == NEW_YORK_TODAY


def test_invoice_form_dates_today_in_firm_zone(new_york_evening):
    form = InvoiceForm()
    assert form.fields["date_issued"].initial == NEW_YORK_TODAY
    assert form.fields["date_limit"].initial == date(2025, 12, 31)


def test_bulk_create_dialog_dates_today_in_firm_zone(client, matter, new_york_evening):
    session = client.session
    session["selected_unbilled"] = [matter.id]
    session.save()
    # The daily check-in is dated by the same clock.
    client.get("/dash/")

    response = client.get(reverse("invoicing:unbilled-bulk-create-invoices"))

    assert response.status_code == 200
    assert response.context["date_issued"] == "2026-01-01"
    assert response.context["date_limit"] == "2025-12-31"
