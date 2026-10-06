"""Agent mode's case-law research needs the Research permission.

The CourtListener tools are offered to the model, and run, only for a user
who could open the Research tab. The case law already saved on the matter
is matter material and stays readable.
"""

import json

import pytest

from apps.accounts.models import CustomUser
from apps.case.ai.agent_prompt import build_agent_system
from apps.case.ai.agent_tools import (
    RESEARCH_TOOLS,
    build_agent_tools,
    make_agent_executor,
)
from apps.case.ai.models import Conversation, Message
from apps.case.models import CaseLaw

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_semantic_pass(monkeypatch):
    monkeypatch.setattr("apps.case.ai.agent_tools.semantic_entries", lambda *a, **k: [])


@pytest.fixture
def no_research():
    return CustomUser.objects.create(
        username="no-research", email="no-research@example.com", perm_research=False
    )


@pytest.fixture
def courtlistener(monkeypatch):
    """Record every call that would reach CourtListener."""
    calls = []

    def fake_search(query, **kwargs):
        calls.append(("search", query))
        return [], 200

    def fake_lookup(citation):
        calls.append(("lookup", citation))
        raise AssertionError("lookup should not be reached")

    def fake_cluster(cluster_id):
        calls.append(("cluster", cluster_id))
        return None

    monkeypatch.setattr("apps.case.courtlistener.search_opinions", fake_search)
    monkeypatch.setattr("apps.case.courtlistener.lookup_citation", fake_lookup)
    monkeypatch.setattr("apps.case.courtlistener.fetch_cluster", fake_cluster)
    return calls


def run(execute_batch, name, **kwargs):
    outcome = execute_batch([{"id": "c1", "name": name, "input": kwargs}])[0]
    return json.loads(outcome["content"]), outcome


def test_research_tools_are_offered_only_with_research():
    offered = {t["name"] for t in build_agent_tools(include_research=True)}
    withheld = {t["name"] for t in build_agent_tools(include_research=False)}
    assert set(RESEARCH_TOOLS) <= offered
    assert not set(RESEARCH_TOOLS) & withheld
    # Saved case law is the matter's own material.
    assert "read_caselaw" in withheld


@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("search_caselaw", {"query": "spoliation sanctions", "state": "ga"}),
        ("lookup_citation", {"citation": "267 Ga. App. 431"}),
        ("read_opinion", {"cluster_id": 987654}),
        ("search_in_opinions", {"cluster_ids": [987654], "query": "spoliation"}),
    ],
)
def test_research_tools_refuse_without_research(
    matter, no_research, courtlistener, name, kwargs
):
    execute = make_agent_executor(matter, None, user=no_research)
    payload, outcome = run(execute, name, **kwargs)
    assert outcome["is_error"]
    assert "Research" in payload["error"]
    assert courtlistener == []


def test_search_runs_with_research(matter, user, courtlistener):
    execute = make_agent_executor(matter, None, user=user)
    _, outcome = run(execute, "search_caselaw", query="spoliation", state="ga")
    assert not outcome["is_error"]
    assert courtlistener == [("search", "spoliation")]


def test_admin_passes_whatever_the_flag_says(matter, courtlistener):
    admin = CustomUser.objects.create(
        username="boss", email="boss@example.com", role="ADMIN", perm_research=False
    )
    execute = make_agent_executor(matter, None, user=admin)
    _, outcome = run(execute, "search_caselaw", query="spoliation", state="ga")
    assert not outcome["is_error"]


def test_saved_case_law_stays_readable(matter, no_research, monkeypatch):
    monkeypatch.setattr(
        "apps.case.ai.context._fetch_caselaw_opinion_text", lambda caselaw: ""
    )
    case = CaseLaw.objects.create(
        matter=matter,
        case_name="Smith v. Jones",
        citation="1 Ga. 1",
        court="Supreme Court of Georgia",
        summary="Held that spoliation requires notice.",
    )
    execute = make_agent_executor(matter, None, user=no_research)
    payload, outcome = run(execute, "read_caselaw", caselaw_id=case.id)
    assert not outcome["is_error"]


def test_prompt_carries_the_research_method_only_with_research(
    matter, user, no_research
):
    conversation = Conversation.objects.create(
        matter=matter, title="Agent", kind="agent", user=user
    )
    Message.objects.create(
        conversation=conversation,
        role="user",
        content="Research this and save the cases to case law.",
        user=user,
    )
    message = "Research this and save the cases to case law."

    segments, _ = build_agent_system(matter, user, conversation, message)
    assert "## Legal Research Method" in segments[0]
    assert "save-caselaw" in segments[2]

    segments, _ = build_agent_system(matter, no_research, conversation, message)
    assert "## Legal Research Method" not in segments[0]
    assert "save-caselaw" not in segments[2]
