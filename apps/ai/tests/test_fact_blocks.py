"""Tests for AI-created timeline facts (create-facts fenced blocks)."""

import datetime
import json

import pytest

from apps.ai.fact_blocks import FACTS_PROTOCOL, apply_fact_blocks
from apps.case.models import Fact

pytestmark = pytest.mark.django_db


def block(entries):
    return "Done.\n\n```create-facts\n" + json.dumps(entries) + "\n```"


# ── Block parsing ────────────────────────────────────────────────────────────


def test_fact_block_creates_fact(user, matter):
    text = apply_fact_blocks(
        block(
            [
                {
                    "date": "2024-03-15",
                    "time": "14:30",
                    "description": "Demand letter sent to opposing counsel",
                    "color": "red",
                    "importance": 9,
                }
            ]
        ),
        matter,
        user,
    )
    fact = Fact.objects.get()
    assert fact.matter_id == matter.id
    assert fact.user_id == user.id
    assert fact.date == datetime.date(2024, 3, 15)
    assert fact.time == datetime.time(14, 30)
    assert fact.description == "Demand letter sent to opposing counsel"
    assert fact.color == "Red"  # normalized to the stored choice value
    assert fact.importance == 7  # clamped
    assert "Added to timeline: **Demand letter sent to opposing counsel**" in text
    assert "```create-facts" not in text


def test_optional_fields_default(user, matter):
    apply_fact_blocks(block([{"description": "Complaint filed"}]), matter, user)
    fact = Fact.objects.get()
    assert fact.date is None
    assert fact.time is None
    assert fact.color is None
    assert fact.importance == 4


def test_bad_optional_fields_degrade(user, matter):
    apply_fact_blocks(
        block(
            [
                {
                    "date": "sometime in March",
                    "time": "afternoon",
                    "description": "Deposition of Dr. Reed",
                    "color": "chartreuse",
                    "importance": "high",
                }
            ]
        ),
        matter,
        user,
    )
    fact = Fact.objects.get()
    assert fact.date is None
    assert fact.time is None
    assert fact.color is None
    assert fact.importance == 4


def test_long_description_truncated(user, matter):
    apply_fact_blocks(block([{"description": "x" * 200}]), matter, user)
    assert len(Fact.objects.get().description) == 150


def test_short_description_skipped(user, matter):
    text = apply_fact_blocks(block([{"description": "ab"}]), matter, user)
    assert Fact.objects.count() == 0
    assert "(no facts created)" in text


def test_invalid_json_left_alone(user, matter):
    text = "```create-facts\nnot json at all\n```"
    result = apply_fact_blocks(text, matter, user)
    assert result == text
    assert Fact.objects.count() == 0


def test_non_list_left_alone(user, matter):
    text = '```create-facts\n{"description": "not a list"}\n```'
    result = apply_fact_blocks(text, matter, user)
    assert result == text
    assert Fact.objects.count() == 0


def test_documents_attached_as_sources(user, matter, document):
    text = apply_fact_blocks(
        block(
            [
                {
                    "date": "2024-03-15",
                    "description": "Complaint filed",
                    "documents": [document.id],
                }
            ]
        ),
        matter,
        user,
    )
    fact = Fact.objects.get()
    assert [doc.id for doc in fact.documents.all()] == [document.id]
    assert f"source: {document.name}" in text


def test_highlights_attached_as_sources(user, matter, highlight):
    text = apply_fact_blocks(
        block(
            [
                {
                    "date": "2024-03-15",
                    "description": "Complaint filed",
                    "highlights": [highlight.id],
                }
            ]
        ),
        matter,
        user,
    )
    fact = Fact.objects.get()
    assert [hl.id for hl in fact.highlights.all()] == [highlight.id]
    assert f"source: {highlight.citation}" in text


def test_foreign_and_bad_source_ids_dropped(user, matter, document, highlight, contact):
    from apps.matters.models import Matter

    other = Matter.objects.create(name="Other Matter", client=contact)
    foreign_doc = document.__class__.objects.create(
        matter=other, name="Foreign Doc", ocr_status="not_applicable"
    )
    foreign_hl = highlight.__class__.objects.create(
        document=foreign_doc, slug="Foreign", text="other matter text"
    )
    apply_fact_blocks(
        block(
            [
                {
                    "description": "Complaint filed",
                    "documents": [foreign_doc.id, "abc", None, 999999],
                    "highlights": [foreign_hl.id, "xyz", 999999],
                }
            ]
        ),
        matter,
        user,
    )
    fact = Fact.objects.get()
    assert fact.documents.count() == 0
    assert fact.highlights.count() == 0


def test_multiple_entries_in_order(user, matter):
    text = apply_fact_blocks(
        block(
            [
                {"date": "2024-01-05", "description": "Contract signed"},
                {"date": "2024-02-10", "description": "First missed payment"},
            ]
        ),
        matter,
        user,
    )
    assert Fact.objects.count() == 2
    assert text.index("Contract signed") < text.index("First missed payment")


def test_protocol_mentions_only_valid_colors():
    for value in ("Blue", "Gray", "Green", "Orange", "Purple", "Red", "Yellow"):
        assert value in FACTS_PROTOCOL
