"""Agent tools: handlers, budget, dedupe, and the parallel batch runner."""

import json
import time
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.ai.agent_tools import (
    AgentBudget,
    build_agent_tools,
    make_agent_executor,
    run_tool_batch,
)
from apps.mail.models import Email

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _no_semantic_pass(monkeypatch):
    """These tests exercise the keyword and fuzzy paths; the semantic
    pass is faked out (test_semantic.py covers it)."""
    monkeypatch.setattr("apps.ai.agent_tools.semantic_entries", lambda *a, **k: [])


def call(name, **kwargs):
    return {"id": f"call_{name}", "name": name, "input": kwargs}


def run(execute_batch, name, **kwargs):
    outcome = execute_batch([call(name, **kwargs)])[0]
    return json.loads(outcome["content"]), outcome


@pytest.fixture
def text_document(document):
    document.ocr_text = "Alpha " * 50 + "spoliation letter " + "omega " * 50
    document.ocr_status = "completed"
    document.save(update_fields=["ocr_text", "ocr_status"])
    return document


@pytest.fixture
def executor(matter, user):
    # The executor works for a user: this one holds every permission.
    events = []
    execute = make_agent_executor(matter, None, on_event=events.append, user=user)
    execute.events = events
    return execute


class TestSpecs:
    def test_every_tool_has_a_schema(self):
        specs = build_agent_tools()
        names = {spec["name"] for spec in specs}
        assert {"search_materials", "read_document", "read_matter_section"} <= names
        for spec in specs:
            assert spec["input_schema"]["type"] == "object"
            assert spec["description"]


class TestReadDocument:
    def test_full_read(self, executor, text_document):
        payload, outcome = run(executor, "read_document", doc_id=text_document.id)
        assert not outcome["is_error"]
        assert payload["text"] == text_document.ocr_text
        assert payload["next_offset"] is None
        assert payload["budget"]["calls_left"] == 39
        step = executor.events[-1]
        assert step["type"] == "tool" and not step["pending"]
        assert step["label"].startswith("Read *Test Document*")
        assert step["title"] == "Read *Test Document*"
        assert step["detail"].endswith("chars")
        assert step["chars"] == len(text_document.ocr_text)

    def test_parts(self, matter, text_document):
        budget = AgentBudget(default_read_chars=100, max_read_chars=100)
        execute = make_agent_executor(matter, None, budget=budget)
        first, _ = run(execute, "read_document", doc_id=text_document.id)
        assert len(first["text"]) == 100
        assert first["truncated"] and first["next_offset"] == 100
        second, _ = run(
            execute,
            "read_document",
            doc_id=text_document.id,
            offset=first["next_offset"],
        )
        assert second["text"] == text_document.ocr_text[100:200]
        assert second["offset"] == 100

    def test_never_document_refused(self, executor, text_document):
        text_document.ai_context = "never"
        text_document.save(update_fields=["ai_context"])
        payload, outcome = run(executor, "read_document", doc_id=text_document.id)
        assert outcome["is_error"]
        assert "excluded" in payload["error"]

    def test_unknown_document(self, executor):
        payload, outcome = run(executor, "read_document", doc_id=999_999)
        assert outcome["is_error"]
        assert executor.events[-1]["error"]
        # The elbow line carries the error; the call line keeps its title.
        assert executor.events[-1]["title"].startswith("Reading document")

    def test_no_text(self, executor, document):
        payload, outcome = run(executor, "read_document", doc_id=document.id)
        assert outcome["is_error"]
        assert "no extracted text" in payload["error"]

    def test_summary_and_description_in_payload(self, executor, text_document):
        text_document.description = "Letter to opposing counsel"
        text_document.summary = "A preservation demand covering the ESI at issue."
        text_document.save(update_fields=["description", "summary"])
        payload, outcome = run(executor, "read_document", doc_id=text_document.id)
        assert not outcome["is_error"]
        assert payload["description"] == "Letter to opposing counsel"
        assert payload["summary"] == (
            "A preservation demand covering the ESI at issue."
        )

    def test_blank_summary_and_description_omitted(self, executor, text_document):
        text_document.description = ""
        text_document.summary = None
        text_document.save(update_fields=["description", "summary"])
        payload, outcome = run(executor, "read_document", doc_id=text_document.id)
        assert not outcome["is_error"]
        assert "description" not in payload
        assert "summary" not in payload


class TestBudget:
    def test_repeat_is_free_and_flagged(self, executor, text_document):
        run(executor, "read_document", doc_id=text_document.id)
        payload, outcome = run(executor, "read_document", doc_id=text_document.id)
        assert not outcome["is_error"]
        assert "already made this exact call" in payload["note"]
        assert payload["text"] == text_document.ocr_text
        assert executor.events[-1]["repeat"] is True
        assert executor.events[-1]["detail"].endswith("repeat, not charged")
        usage = executor.usage()
        assert usage["tool_calls"] == 1
        assert usage["chars_read"] == len(text_document.ocr_text)

    def test_call_cap(self, matter):
        execute = make_agent_executor(
            matter, None, budget=AgentBudget(max_tool_calls=2)
        )
        run(execute, "read_matter_section", section="overview")
        run(execute, "read_matter_section", section="contacts")
        payload, outcome = run(execute, "read_matter_section", section="tasks")
        assert outcome["is_error"]
        assert "Tool budget exhausted" in payload["error"]
        assert execute.usage()["tool_calls"] == 2

    def test_read_cap(self, matter, text_document):
        execute = make_agent_executor(matter, None, budget=AgentBudget(max_chars=10))
        first, _ = run(execute, "read_document", doc_id=text_document.id)
        assert len(first["text"]) == 10
        payload, outcome = run(execute, "read_matter_section", section="overview")
        assert outcome["is_error"]
        assert "Reading budget exhausted" in payload["error"]

    def test_unknown_tool(self, executor):
        payload, outcome = run(executor, "open_material", x=1)
        assert outcome["is_error"]
        assert "Unknown tool" in payload["error"]

    def test_cancelled(self, matter, text_document):
        execute = make_agent_executor(matter, None, is_cancelled=lambda: True)
        payload, outcome = run(execute, "read_document", doc_id=text_document.id)
        assert outcome["is_error"]
        assert execute.usage()["tool_calls"] == 0


class TestSearch:
    def test_hits_and_seen_flags(self, executor, text_document, fact):
        from watson import search as watson

        watson.default_search_engine.update_obj_index(text_document)
        payload, outcome = run(executor, "search_materials", query="spoliation")
        assert not outcome["is_error"]
        kinds = {hit["kind"] for hit in payload["hits"]}
        assert "document" in kinds
        doc_hit = next(h for h in payload["hits"] if h["kind"] == "document")
        assert doc_hit["handle"] == f"doc:{text_document.id}"
        assert "spoliation" in doc_hit["snippet"]
        assert "summary" not in doc_hit
        assert doc_hit["seen"] is False
        assert executor.events[-1]["label"].startswith('Searched "spoliation"')
        assert executor.events[-1]["title"] == 'Searched "spoliation"'
        assert "hits" in executor.events[-1]["detail"]

        again, _ = run(executor, "search_materials", query="spoliation letter")
        assert any(h["seen"] for h in again["hits"])

    def test_email_hits(self, executor, matter):
        from watson import search as watson

        email = Email.objects.create(
            matter=matter,
            gmail_id="m1",
            thread_id="t1",
            sender="oc@example.com",
            recipients="james@example.com",
            subject="Depo dates",
            body_text="How about the spoliation letter on Tuesday?",
            date=timezone.now(),
        )
        watson.default_search_engine.update_obj_index(email)
        payload, _ = run(
            executor, "search_materials", query="spoliation", kinds=["email"]
        )
        assert payload["hits"][0]["handle"] == "thread:t1"
        assert payload["hits"][0]["name"] == "Depo dates"
        assert "spoliation" in payload["hits"][0]["snippet"]

    def test_phrase_or_and_variants(self, executor, matter, user):
        from watson import search as watson

        from apps.case.models import Fact

        fact_a = Fact.objects.create(
            matter=matter,
            date="2024-01-25",
            description="The earnest money deposit was returned to the buyer.",
        )
        fact_b = Fact.objects.create(
            matter=matter,
            date="2024-01-26",
            description="Money for the deposit arrived by wire.",
        )
        for fact in (fact_a, fact_b):
            watson.default_search_engine.update_obj_index(fact)

        phrase, _ = run(
            executor, "search_materials", query='"earnest money"', kinds=["fact"]
        )
        assert [h["id"] for h in phrase["hits"]] == [fact_a.id]

        either, _ = run(
            executor, "search_materials", query="earnest OR wire", kinds=["fact"]
        )
        assert {h["id"] for h in either["hits"]} == {fact_a.id, fact_b.id}

        merged, outcome = run(
            executor,
            "search_materials",
            queries=["earnest money", "deposit arrived"],
            kinds=["fact"],
        )
        by_id = {h["id"]: h for h in merged["hits"]}
        assert by_id[fact_a.id]["matched"] == ["earnest money"]
        assert by_id[fact_b.id]["matched"] == ["deposit arrived"]
        step = executor.events[-1]
        assert step["title"] == 'Searched "earnest money" and 1 more'
        assert "2 hits" in step["detail"]

    def test_document_summary_in_hits(self, executor, matter, user, text_document):
        from watson import search as watson

        text_document.summary = "A preservation demand covering the ESI at issue."
        text_document.save(update_fields=["summary"])
        watson.default_search_engine.update_obj_index(text_document)
        payload, _ = run(executor, "search_materials", query="spoliation")
        by_kind = {h["kind"]: h for h in payload["hits"]}
        assert by_kind["document"]["summary"] == (
            "A preservation demand covering the ESI at issue."
        )

    def test_fuzzy_fallback_on_typo(self, executor, matter, document):
        from watson import search as watson

        document.name = "Spoliation Letter"
        document.description = "Preservation demand sent to opposing counsel."
        document.save(update_fields=["name", "description"])
        watson.default_search_engine.update_obj_index(document)
        payload, outcome = run(
            executor, "search_materials", query="spoilation leter", kinds=["document"]
        )
        assert not outcome["is_error"]
        assert "near matches" in payload["note"]
        assert payload["hits"][0]["id"] == document.id
        assert payload["hits"][0]["fuzzy"] is True

    def test_empty_query(self, executor):
        payload, outcome = run(executor, "search_materials", query="  ")
        assert outcome["is_error"]


class TestOtherReads:
    def test_email_thread(self, executor, matter):
        for i in range(2):
            Email.objects.create(
                matter=matter,
                gmail_id=f"m{i}",
                thread_id="t9",
                sender="oc@example.com",
                recipients="james@example.com",
                subject="Depo dates",
                body_text=f"Body {i}",
                date=timezone.now() - timedelta(days=2 - i),
            )
        payload, outcome = run(executor, "read_email_thread", thread_id="t9")
        assert not outcome["is_error"]
        assert payload["messages"] == 2
        assert "Body 0" in payload["text"] and "Body 1" in payload["text"]
        assert executor.events[-1]["kind"] == "email"

    def test_matter_section(self, executor, matter):
        payload, outcome = run(executor, "read_matter_section", section="overview")
        assert not outcome["is_error"]
        assert "Test Matter" in payload["text"]
        payload, outcome = run(executor, "read_matter_section", section="nope")
        assert outcome["is_error"]

    def test_money_sections_are_not_agent_readable(self, executor):
        for section in ("ledger", "trust"):
            payload, outcome = run(executor, "read_matter_section", section=section)
            assert outcome["is_error"]
            assert "ledger" not in payload["error"]


class TestBatchRunner:
    def test_order_preserved_with_parallel_workers(self):
        calls = [{"id": str(i), "name": "t", "input": {"i": i}} for i in range(6)]

        def slow_then_fast(call):
            time.sleep(0.05 * (5 - call["input"]["i"]))
            return {"id": call["id"], "name": "t", "content": "{}", "is_error": False}

        outcomes = run_tool_batch(calls, slow_then_fast, max_workers=4)
        assert [o["id"] for o in outcomes] == [str(i) for i in range(6)]

    def test_inline_path(self):
        seen = []

        def record(call):
            seen.append(call["id"])
            return {"id": call["id"], "name": "t", "content": "{}", "is_error": False}

        run_tool_batch([{"id": "a", "name": "t", "input": {}}], record, max_workers=4)
        run_tool_batch(
            [
                {"id": "b", "name": "t", "input": {}},
                {"id": "c", "name": "t", "input": {}},
            ],
            record,
            max_workers=1,
        )
        assert seen == ["a", "b", "c"]

    def test_handler_exception_becomes_error_outcome(self, matter, text_document):
        # Inline path: pool threads would open their own DB connections and
        # miss the test transaction's rows.
        execute = make_agent_executor(
            matter, None, budget=AgentBudget(parallel_workers=1)
        )
        outcomes = execute(
            [
                call("read_document", doc_id=text_document.id),
                call("read_matter_section", section="overview"),
                call("read_document", doc_id="not-an-id"),
            ]
        )
        assert [o["is_error"] for o in outcomes] == [False, False, True]
        assert [o["id"] for o in outcomes] == [
            "call_read_document",
            "call_read_matter_section",
            "call_read_document",
        ]
