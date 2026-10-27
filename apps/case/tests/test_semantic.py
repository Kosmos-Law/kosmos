"""Semantic index: chunking, hashing, scoping, and the hybrid search."""

import pytest

from apps.ai.agent_tools import make_agent_executor
from apps.case import semantic
from apps.case.models import Fact, MaterialChunk
from apps.case.semantic import chunk_text, index_object, semantic_entries

pytestmark = pytest.mark.django_db

# Deterministic fake embeddings: one dimension per topic, with "dog" and
# "canine" sharing a dimension so meaning-not-words retrieval is testable.
TOPIC_DIMS = {"dog": 0, "canine": 0, "money": 1, "court": 2}


def fake_vector(text):
    values = [0.0] * 768
    lowered = text.lower()
    hit = False
    for word, dim in TOPIC_DIMS.items():
        if word in lowered:
            values[dim] = 1.0
            hit = True
    if not hit:
        values[10] = 1.0
    return values


def make_fact(matter, description):
    return Fact.objects.create(
        matter=matter, date="2024-01-25", description=description
    )


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(
        semantic,
        "embed_texts",
        lambda texts, task_type="RETRIEVAL_DOCUMENT": [fake_vector(t) for t in texts],
    )
    monkeypatch.setattr(
        semantic, "embed_queries", lambda queries: [fake_vector(q) for q in queries]
    )


class TestChunker:
    def test_short_text_is_one_chunk(self):
        assert chunk_text("hello world") == ["hello world"]

    def test_empty(self):
        assert chunk_text("   ") == []

    def test_long_text_chunks_and_overlaps(self):
        text = "\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(40))
        chunks = chunk_text(text)
        assert len(chunks) > 2
        assert all(len(c) <= semantic.CHUNK_CHARS for c in chunks)
        # Consecutive chunks share an overlap region.
        assert chunks[0][-150:-50] in chunks[1]


class TestIndexObject:
    def test_hash_skip_and_reindex(self, matter, monkeypatch):
        fact = make_fact(matter, "the dog")
        assert index_object("fact", fact) == 1
        chunk = MaterialChunk.objects.get()
        assert chunk.kind == "fact" and chunk.matter_id == matter.id

        calls = []
        monkeypatch.setattr(
            semantic,
            "embed_texts",
            lambda texts, **kw: calls.append(1) or [fake_vector(t) for t in texts],
        )
        assert index_object("fact", fact) == 0
        assert calls == []  # unchanged content never re-embeds

        fact.description = "the money"
        fact.save(update_fields=["description"])
        assert index_object("fact", fact) == 1
        assert calls and MaterialChunk.objects.count() == 1

    def test_never_document_drops_out(self, document):
        document.ocr_text = "the dog agreement"
        document.ocr_status = "completed"
        document.save(update_fields=["ocr_text", "ocr_status"])
        assert index_object("document", document) == 1

        document.ai_context = "never"
        document.save(update_fields=["ai_context"])
        assert index_object("document", document) == 0
        assert MaterialChunk.objects.count() == 0


class TestRetrieval:
    def test_ranked_and_matter_scoped(self, matter, user, contact, practice_area):
        from apps.matters.models import Matter

        near = make_fact(matter, "the dog")
        far = make_fact(matter, "the money")
        other_matter = Matter.objects.create(
            user=user,
            name="Other",
            status="Open",
            date_start="2024-01-01",
            practice_area=practice_area,
            client=contact,
        )
        leaked = make_fact(other_matter, "dog")
        for fact in (near, far, leaked):
            index_object("fact", fact)

        rows = semantic_entries(["dog"], matter, ["fact"], 5)
        assert [r["object_id"] for r in rows[0]] == [near.id]
        assert rows[0][0]["similarity"] >= 0.99

    def test_embedding_failure_degrades_to_empty(self, matter, monkeypatch):
        def boom(queries):
            raise RuntimeError("api down")

        monkeypatch.setattr(semantic, "embed_queries", boom)
        assert semantic_entries(["x"], matter, ["fact"], 5) == []


class TestHybridSearch:
    def test_meaning_only_hit_is_flagged_semantic(self, matter):
        import json

        fact = make_fact(matter, "the canine companion")
        index_object("fact", fact)

        execute = make_agent_executor(matter, None)
        outcome = execute(
            [
                {
                    "id": "t",
                    "name": "search_materials",
                    "input": {"query": "dog", "kinds": ["fact"]},
                }
            ]
        )[0]
        payload = json.loads(outcome["content"])
        assert payload["hits"], payload
        hit = payload["hits"][0]
        assert hit["handle"] == f"fact:{fact.id}"
        assert hit["semantic"] is True
        assert hit["matched"] == ["dog"]

    def test_keyword_and_semantic_agree_without_flag(self, matter):
        import json

        from watson import search as watson

        fact = make_fact(matter, "the dog was walked")
        watson.default_search_engine.update_obj_index(fact)
        index_object("fact", fact)

        execute = make_agent_executor(matter, None)
        outcome = execute(
            [
                {
                    "id": "t",
                    "name": "search_materials",
                    "input": {"query": "dog", "kinds": ["fact"]},
                }
            ]
        )[0]
        payload = json.loads(outcome["content"])
        hit = payload["hits"][0]
        assert hit["handle"] == f"fact:{fact.id}"
        assert "semantic" not in hit
