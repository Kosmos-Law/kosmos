"""Money in the AI's context needs the Financial permission.

The classic context, the agent's index and tools, and the token API's
sections are each built for the user who is asking: without the permission
there are no rates, fees or invoices, though the work itself (who did what,
for how long) is still described.
"""

import json

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts.models import CustomUser
from apps.activity.time.models import TimeEntry
from apps.case.ai import selector
from apps.case.ai.agent_prompt import build_agent_system
from apps.case.ai.agent_tools import build_agent_tools, make_agent_executor
from apps.case.ai.context import (
    assemble_matter_context,
    assemble_matter_context_with_selection,
    format_time_entries,
)
from apps.case.ai.models import Conversation
from apps.case.ai.selector import build_manifest
from apps.drafts.models import CompanionToken
from apps.invoicing.invoices.models import Invoice
from apps.matters.rates.models import Rate

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_semantic_pass(monkeypatch):
    monkeypatch.setattr("apps.case.ai.agent_tools.semantic_entries", lambda *a, **k: [])


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
    """A matter with an invoiced time entry at $275/hr and a matter rate."""
    TimeEntry.objects.create(
        matter=matter,
        user=user,
        date="2026-01-05",
        actions="Draft complaint",
        hours=2,
        rate=275,
        invoice=invoice,
    )
    Rate.objects.create(user=user, matter=matter, matter_rate=275)
    return matter


def run(execute_batch, name, **kwargs):
    outcome = execute_batch([{"id": "c1", "name": name, "input": kwargs}])[0]
    return json.loads(outcome["content"]), outcome


def assert_no_money(text):
    assert "275" not in text
    assert "$" not in text
    assert "Invoice #" not in text


class TestClassicContext:
    def test_time_entries_without_financial_keep_the_work_only(
        self, billed_matter, no_financial
    ):
        text = format_time_entries(billed_matter, include_financial=False)
        assert "Draft complaint" in text
        assert "h by " in text
        assert "2026-01-05" in text
        assert_no_money(text)

    def test_time_entries_default_to_no_money(self, billed_matter):
        assert_no_money(format_time_entries(billed_matter))

    def test_time_entries_with_financial_carry_rate_fee_and_invoice(
        self, billed_matter, invoice
    ):
        text = format_time_entries(billed_matter, include_financial=True)
        assert "$275" in text
        assert "$550.00" in text
        assert f"Invoice #{invoice.id}" in text

    def test_assembled_context_follows_the_user(
        self, billed_matter, user, no_financial, admin_without_flag
    ):
        assert "$550.00" in assemble_matter_context(billed_matter, user=user)
        assert "$550.00" in assemble_matter_context(
            billed_matter, user=admin_without_flag
        )
        limited = assemble_matter_context(billed_matter, user=no_financial)
        assert "Draft complaint" in limited
        assert "$550.00" not in limited
        assert "$275" not in limited

    def test_no_user_means_no_money(self, billed_matter):
        """The nightly auto-summary runs for no user, and every member of
        the matter reads what it writes."""
        text = assemble_matter_context(billed_matter, user=None)
        assert "Draft complaint" in text
        assert "$550.00" not in text

    def test_invoices_are_offered_only_with_financial(self, billed_matter):
        offered, _ = build_manifest(billed_matter, include_invoices=True)
        withheld, _ = build_manifest(billed_matter)
        assert [i.item_type for i in offered if i.item_type == "invoice"]
        assert not [i for i in withheld if i.item_type == "invoice"]

    def test_selection_is_built_for_the_user(
        self, billed_matter, user, no_financial, monkeypatch
    ):
        seen = []

        def fake_manifest(matter, **kwargs):
            seen.append(kwargs.get("include_invoices"))
            return [], {}

        monkeypatch.setattr(selector, "build_manifest", fake_manifest)
        for requester in (user, no_financial):
            assemble_matter_context_with_selection(
                billed_matter,
                user_message="billing?",
                llm="claude-opus",
                user=requester,
            )
        assert seen == [True, False]


class TestContextReuse:
    """The assembled context is cached per conversation. One built for a
    user who may see money must never be handed to one who may not."""

    @pytest.fixture
    def conversation(self, billed_matter):
        cache.clear()
        return Conversation.objects.create(
            matter=billed_matter, title="Shared chat", llm="claude-opus"
        )

    def _assemble(self, matter, conversation, user):
        return assemble_matter_context_with_selection(
            matter,
            user_message="what was billed?",
            llm="claude-opus",
            user=user,
            conversation=conversation,
        )

    def test_second_user_gets_their_own_context(
        self, billed_matter, conversation, user, no_financial
    ):
        first = self._assemble(billed_matter, conversation, user)
        assert "$550.00" in first
        second = self._assemble(billed_matter, conversation, no_financial)
        assert "$550.00" not in second

    def test_losing_the_permission_drops_the_cached_context(
        self, billed_matter, conversation, user
    ):
        assert "$550.00" in self._assemble(billed_matter, conversation, user)
        user.perm_financial = False
        user.save()
        assert "$550.00" not in self._assemble(billed_matter, conversation, user)


class TestAgentMode:
    def test_invoice_tool_is_offered_only_with_financial(self):
        with_money = {t["name"] for t in build_agent_tools(include_financial=True)}
        without = {t["name"] for t in build_agent_tools(include_financial=False)}
        assert "read_invoice" in with_money
        assert "read_invoice" not in without

    def test_money_sections_are_offered_only_with_financial(self):
        def sections(include_financial):
            spec = next(
                t
                for t in build_agent_tools(include_financial=include_financial)
                if t["name"] == "read_matter_section"
            )
            return spec["input_schema"]["properties"]["section"]["enum"], spec

        enum, spec = sections(True)
        assert {"rates", "activity"} <= set(enum)
        enum, spec = sections(False)
        assert not {"rates", "activity"} & set(enum)
        assert "rates" not in spec["description"]

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

    @pytest.mark.parametrize("section", ["rates", "activity"])
    def test_money_sections_refused_without_financial(
        self, billed_matter, no_financial, section
    ):
        execute = make_agent_executor(billed_matter, None, user=no_financial)
        payload, outcome = run(execute, "read_matter_section", section=section)
        assert outcome["is_error"]
        assert "275" not in outcome["content"]

    @pytest.mark.parametrize("section", ["rates", "activity"])
    def test_money_sections_served_with_financial(self, billed_matter, user, section):
        execute = make_agent_executor(billed_matter, None, user=user)
        payload, outcome = run(execute, "read_matter_section", section=section)
        assert not outcome["is_error"]
        assert "$275" in payload["text"]

    def test_an_executor_with_no_user_serves_no_money(self, billed_matter, invoice):
        execute = make_agent_executor(billed_matter, None)
        _, outcome = run(execute, "read_invoice", invoice_id=invoice.id)
        assert outcome["is_error"]
        _, outcome = run(execute, "read_matter_section", section="rates")
        assert outcome["is_error"]

    def test_index_lists_invoices_only_with_financial(
        self, billed_matter, invoice, user, no_financial
    ):
        conversation = Conversation.objects.create(
            matter=billed_matter, title="Agent", kind="agent"
        )
        handle = f"[inv:{invoice.id}]"
        segments, _ = build_agent_system(billed_matter, user, conversation, "billing?")
        assert handle in segments[0]
        segments, _ = build_agent_system(
            billed_matter, no_financial, conversation, "billing?"
        )
        assert handle not in segments[0]
        assert "balance $" not in segments[0]


class TestTokenApi:
    """The Claude Desktop API serves the same sections under the same rule."""

    @pytest.mark.parametrize("section", ["rates", "activity", "ledger", "trust"])
    def test_money_sections_need_financial(self, billed_matter, no_financial, section):
        api = Client(HTTP_X_KOSMOS_TOKEN=CompanionToken.for_user(no_financial).key)
        response = api.get(f"/case/api/matter/{billed_matter.id}/{section}/")
        assert response.status_code == 403
        assert b"275" not in response.content

    @pytest.mark.parametrize("section", ["rates", "activity"])
    def test_money_sections_served_with_financial(self, billed_matter, user, section):
        api = Client(HTTP_X_KOSMOS_TOKEN=CompanionToken.for_user(user).key)
        response = api.get(f"/case/api/matter/{billed_matter.id}/{section}/")
        assert response.status_code == 200
        assert "$275" in response.json()["text"]
