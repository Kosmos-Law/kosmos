"""What the AI may say about money, and to whom.

The rule follows the application's own screens. Time entries carry their
rate, fee, comp flag and invoice status for every user who can see the
matter, as the Activity screens do. Invoices, the rates section, the ledger
and trust are behind the Financial permission, as the Invoicing, Rates and
Ledger screens are. A run for no user carries no billing detail at all.
The matter tools here are the ones a session serves (session_tools.py);
the token API (and the MCP server over it) applies the same rule.
"""

import json

import pytest
from django.test import Client

from apps.accounts.models import ApiToken, CustomUser
from apps.activity.time.models import TimeEntry
from apps.ai.agent_tools import build_agent_tools, make_agent_executor
from apps.invoicing.invoices.models import Invoice
from apps.matters.rates.models import Rate

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_semantic_pass(monkeypatch):
    monkeypatch.setattr("apps.ai.agent_tools.semantic_entries", lambda *a, **k: [])


@pytest.fixture
def no_financial():
    return CustomUser.objects.create(
        username="paralegal",
        email="paralegal@example.com",
        perm_financial=False,
    )


@pytest.fixture
def admin_without_flag():
    """An admin passes whatever the flag says."""
    return CustomUser.objects.create(
        username="boss", email="boss@example.com", role="ADMIN", perm_financial=False
    )


@pytest.fixture
def invoice(matter):
    return Invoice.objects.create(
        matter=matter, status="SENT", date_limit="2026-01-31", date_issued="2026-02-01"
    )


@pytest.fixture
def billed_matter(matter, user, invoice):
    """A matter with an invoiced time entry (2h at $275/hr, a $550.00 fee)
    and a matter rate of $310/hr on the Rates tab."""
    TimeEntry.objects.create(
        matter=matter,
        user=user,
        date="2026-01-05",
        actions="Draft complaint",
        hours=2,
        rate=275,
        invoice=invoice,
    )
    Rate.objects.create(user=user, matter=matter, matter_rate=310)
    return matter


def run(execute_batch, name, **kwargs):
    outcome = execute_batch([{"id": "c1", "name": name, "input": kwargs}])[0]
    return json.loads(outcome["content"]), outcome


def assert_no_money(text):
    assert "275" not in text
    assert "$" not in text
    assert "Invoice #" not in text


def assert_time_entry_billing(text, invoice):
    assert "Draft complaint" in text
    assert "$275/hr" in text
    assert "$550.00" in text
    assert f"Invoice #{invoice.id}" in text


class TestMatterTools:
    def test_invoice_tool_is_offered_only_with_financial(self):
        with_money = {t["name"] for t in build_agent_tools(include_financial=True)}
        without = {t["name"] for t in build_agent_tools(include_financial=False)}
        assert "read_invoice" in with_money
        assert "read_invoice" not in without

    def test_rates_section_is_offered_only_with_financial(self):
        def sections(include_financial):
            spec = next(
                t
                for t in build_agent_tools(include_financial=include_financial)
                if t["name"] == "read_matter_section"
            )
            return spec["input_schema"]["properties"]["section"]["enum"], spec

        enum, spec = sections(True)
        assert {"rates", "activity"} <= set(enum)
        assert "rates" in spec["description"]

        enum, spec = sections(False)
        assert "rates" not in enum
        assert "rates" not in spec["description"]
        # Activity is open to every user who can see the matter.
        assert "activity" in enum
        assert "activity" in spec["description"]

    def test_read_invoice_refused_without_financial(
        self, billed_matter, invoice, no_financial
    ):
        execute = make_agent_executor(billed_matter, None, user=no_financial)
        payload, outcome = run(execute, "read_invoice", invoice_id=invoice.id)
        assert outcome["is_error"]
        assert "Financial" in payload["error"]
        assert "text" not in payload

    def test_read_invoice_allowed_with_financial(self, billed_matter, invoice, user):
        execute = make_agent_executor(billed_matter, None, user=user)
        payload, outcome = run(execute, "read_invoice", invoice_id=invoice.id)
        assert not outcome["is_error"]
        assert f"Invoice #{invoice.id}" in payload["text"]

    def test_rates_section_refused_without_financial(self, billed_matter, no_financial):
        execute = make_agent_executor(billed_matter, None, user=no_financial)
        payload, outcome = run(execute, "read_matter_section", section="rates")
        assert outcome["is_error"]
        assert "Financial" in payload["error"]
        assert "310" not in outcome["content"]

    def test_rates_section_served_with_financial(self, billed_matter, user):
        execute = make_agent_executor(billed_matter, None, user=user)
        payload, outcome = run(execute, "read_matter_section", section="rates")
        assert not outcome["is_error"]
        assert "$310/hr" in payload["text"]

    def test_activity_section_served_to_every_user(
        self, billed_matter, invoice, user, no_financial
    ):
        for requester in (user, no_financial):
            execute = make_agent_executor(billed_matter, None, user=requester)
            payload, outcome = run(execute, "read_matter_section", section="activity")
            assert not outcome["is_error"]
            assert_time_entry_billing(payload["text"], invoice)

    @pytest.mark.parametrize("section", ["ledger", "trust"])
    def test_ledger_and_trust_stay_out_of_agent_mode(
        self, billed_matter, user, section
    ):
        execute = make_agent_executor(billed_matter, None, user=user)
        _, outcome = run(execute, "read_matter_section", section=section)
        assert outcome["is_error"]

    def test_an_executor_with_no_user_serves_no_invoices_or_rates(
        self, billed_matter, invoice
    ):
        execute = make_agent_executor(billed_matter, None)
        _, outcome = run(execute, "read_invoice", invoice_id=invoice.id)
        assert outcome["is_error"]
        _, outcome = run(execute, "read_matter_section", section="rates")
        assert outcome["is_error"]


class TestTokenApi:
    """The token API serves the same sections under the same rule."""

    @pytest.mark.parametrize("section", ["rates", "ledger", "trust"])
    def test_money_sections_need_financial(self, billed_matter, no_financial, section):
        api = Client(HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(no_financial).key)
        response = api.get(f"/case/api/matter/{billed_matter.id}/{section}/")
        assert response.status_code == 403
        assert b"310" not in response.content

    def test_rates_served_with_financial(self, billed_matter, user):
        api = Client(HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(user).key)
        response = api.get(f"/case/api/matter/{billed_matter.id}/rates/")
        assert response.status_code == 200
        assert "$310/hr" in response.json()["text"]

    def test_activity_served_to_every_user(
        self, billed_matter, invoice, user, no_financial
    ):
        for requester in (user, no_financial):
            api = Client(HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(requester).key)
            response = api.get(f"/case/api/matter/{billed_matter.id}/activity/")
            assert response.status_code == 200
            assert_time_entry_billing(response.json()["text"], invoice)

    def test_invoice_read_needs_financial(self, billed_matter, invoice, no_financial):
        api = Client(HTTP_X_KOSMOS_TOKEN=ApiToken.for_user(no_financial).key)
        response = api.get(f"/case/api/invoices/{invoice.id}/")
        assert response.status_code == 403
