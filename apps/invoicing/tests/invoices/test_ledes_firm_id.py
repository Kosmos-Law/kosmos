"""Download Ledes needs the firm's LEDES ID (LAW_FIRM_ID).

Without it every line of the file would carry a blank LAW_FIRM_ID, which
e-billing systems reject, so the action is hidden and the endpoint refuses.
"""

import pytest
from django.urls import reverse

from apps.invoicing.invoices.functions import ledes_available
from apps.invoicing.invoices.models import Invoice

pytestmark = pytest.mark.django_db


@pytest.fixture
def invoice(user, matter):
    return Invoice.objects.create(
        created_by=user,
        matter=matter,
        date_limit="2024-12-31",
        date_issued="2024-12-01",
        status="SENT",
    )


def detail_html(client, invoice):
    response = client.get(
        reverse("invoicing:invoices-detail-index", kwargs={"pk": invoice.pk})
    )
    assert response.status_code == 200
    return response.content.decode()


def test_ledes_available_follows_law_firm_id(settings):
    settings.LAW_FIRM_ID = ""
    assert not ledes_available()
    settings.LAW_FIRM_ID = "12-3456789"
    assert ledes_available()


def test_download_ledes_hidden_without_firm_id(client, invoice, settings):
    settings.LAW_FIRM_ID = ""
    assert "Download Ledes" not in detail_html(client, invoice)


def test_download_ledes_offered_with_firm_id(client, invoice, settings):
    settings.LAW_FIRM_ID = "12-3456789"
    assert "Download Ledes" in detail_html(client, invoice)


def test_ledes_endpoint_refuses_without_firm_id(client, invoice, settings):
    settings.LAW_FIRM_ID = ""
    response = client.get(reverse("invoicing:invoice-ledes", kwargs={"pk": invoice.pk}))
    assert response.status_code == 400


def test_ledes_endpoint_serves_the_file_with_firm_id(client, invoice, settings):
    settings.LAW_FIRM_ID = "12-3456789"
    response = client.get(reverse("invoicing:invoice-ledes", kwargs={"pk": invoice.pk}))
    assert response.status_code == 200
    assert response.content.startswith(b"LEDES1998B[]")
