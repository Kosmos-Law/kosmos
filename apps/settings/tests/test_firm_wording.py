"""An invoice's trust note and a reminder's payment terms are the firm's own
wording, set under Settings, Firm. Blank leaves them out; nothing about one
firm's fee agreement is written into the templates."""

import pytest
from django.template.loader import render_to_string

from apps.accounts.models import CustomUser
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db

REMINDERS = [
    "emails/invoice_reminder_email.txt",
    "emails/invoice_reminder_email.html",
    "emails/payment_request_reminder_email.txt",
    "emails/payment_request_reminder_email.html",
]


@pytest.mark.parametrize("template", REMINDERS)
def test_a_reminder_says_nothing_about_terms_unless_the_firm_set_them(template):
    blank = render_to_string(template, {"payment_terms": "", "days_since": 5})
    with_terms = render_to_string(
        template, {"payment_terms": "Payment is due within 30 days.", "days_since": 5}
    )

    assert "attorney-client agreement" not in blank
    assert "due upon receipt" not in blank
    assert "Payment is due within 30 days." in with_terms


def test_the_invoice_prints_the_firms_trust_note_only_when_set():
    firm = Firm(name="Example Law")
    context = {"company": firm, "confirmed_balance": 500, "invoice": None}

    blank = render_to_string("invoicing/invoices/invoice.html", context)
    firm.invoice_trust_note = "Funds in trust are applied at the end of the matter."
    with_note = render_to_string("invoicing/invoices/invoice.html", context)

    assert "Paragraph 4.3" not in blank
    assert "trust-caption" not in blank
    assert "Funds in trust are applied at the end of the matter." in with_note


def test_the_firm_form_offers_both(admin_client):
    body = admin_client.get("/settings/firm/").content.decode()

    assert "Payment Terms" in body
    assert "Invoice Trust Note" in body


def test_checklists_are_in_the_settings_menu_for_everyone(client, user):
    # update(), not save(): saving the fixture's copy would undo the "seen
    # the Dash today" mark the client fixture set, and redirect to the Dash.
    CustomUser.objects.filter(pk=user.pk).update(perm_financial=False)

    response = client.get("/settings/profile/", follow=True)
    body = response.content.decode()

    assert response.status_code == 200

    assert "Checklists" in body
