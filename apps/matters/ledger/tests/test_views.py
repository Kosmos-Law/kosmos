import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

pytestmark = pytest.mark.django_db


class TestLedgerIndex:
    def test_renders(self, client, matter, sent_invoice):
        url = reverse("matters:ledger", args=[matter.id])
        response = client.get(url)
        assert response.status_code == 200
        assertTemplateUsed(response, "matters/ledger/list.html")
        assert response.context["matter"] == matter
        assert "transactions" in response.context
        assert "balance_due" in response.context

    def test_nonexistent_matter_404(self, client):
        url = reverse("matters:ledger", args=[99999])
        response = client.get(url)
        assert response.status_code == 404


class TestLedgerList:
    def test_renders(self, client, matter, sent_invoice):
        url = reverse("matters:ledger-list", args=[matter.id])
        response = client.get(url)
        assert response.status_code == 200
        assertTemplateUsed(response, "matters/ledger/list.html")

    def test_includes_trust_balance(self, client, matter):
        url = reverse("matters:ledger-list", args=[matter.id])
        response = client.get(url)
        assert "client_trust_balance" in response.context

    def test_draft_invoice_shown_under_work_in_progress(
        self, client, matter, draft_invoice
    ):
        url = reverse("matters:ledger-list", args=[matter.id])
        response = client.get(url)
        assert response.context["work_in_progress"] == 300
        assert response.context["total_cost"] == 300
        assert f"On Invoice {draft_invoice.id}" in response.content.decode()
