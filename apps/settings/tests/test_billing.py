"""Settings > Billing: the billing email, invoice BCC, payment terms and
invoice trust note, on the Firm record but saved on a tab of their own."""

import pytest

from apps.settings.models import Firm

pytestmark = pytest.mark.django_db


def test_the_billing_tab_holds_the_billing_fields(admin_client):
    Firm.objects.create(name="Firm")

    body = admin_client.get("/settings/billing/").content.decode()

    for field in (
        "billing_email",
        "invoice_bcc",
        "payment_terms",
        "invoice_trust_note",
    ):
        assert f'name="{field}"' in body
    assert 'name="name"' not in body
    assert "Save Billing Settings" in body
    # the tab is in the settings navigation
    assert 'href="/settings/billing/"' in body


def test_saving_billing_leaves_the_firm_details_alone(admin_client):
    Firm.objects.create(name="Example Law", city="Helena", jurisdiction="Montana")

    response = admin_client.post(
        "/settings/billing/",
        {
            "billing_email": "billing@example.com",
            "invoice_bcc": "a@example.com; b@example.com",
            "payment_terms": "Payment is due upon receipt.",
            "invoice_trust_note": "Funds in trust are held to the end of the matter.",
        },
    )

    assert response.status_code == 200
    assert "success" in response.headers.get("HX-Toast", "").lower()
    firm = Firm.objects.get()
    assert firm.billing_email == "billing@example.com"
    assert firm.invoice_bcc == "a@example.com, b@example.com"
    assert firm.payment_terms == "Payment is due upon receipt."
    assert firm.invoice_trust_note.startswith("Funds in trust")
    assert (firm.name, firm.city, firm.jurisdiction) == (
        "Example Law",
        "Helena",
        "Montana",
    )


def test_saving_firm_details_leaves_billing_alone(admin_client):
    Firm.objects.create(
        name="Example Law",
        billing_email="billing@example.com",
        invoice_bcc="a@example.com",
        payment_terms="Payment is due upon receipt.",
        invoice_trust_note="Held to the end of the matter.",
    )

    admin_client.post("/settings/firm/", {"name": "Example Law", "city": "Helena"})

    firm = Firm.objects.get()
    assert firm.city == "Helena"
    assert firm.billing_email == "billing@example.com"
    assert firm.invoice_bcc == "a@example.com"
    assert firm.payment_terms == "Payment is due upon receipt."
    assert firm.invoice_trust_note == "Held to the end of the matter."


def test_a_bad_bcc_address_is_refused(admin_client):
    Firm.objects.create(name="Firm")

    response = admin_client.post(
        "/settings/billing/", {"invoice_bcc": "good@example.com, not-an-address"}
    )

    assert "Invalid email address(es): not-an-address" in response.content.decode()
    assert Firm.objects.get().invoice_bcc == ""
