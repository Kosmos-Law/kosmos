"""Tests for raw context-handle translation (handles.py)."""

import pytest

from apps.ai.handles import resolve_handles_for_chat

pytestmark = pytest.mark.django_db


# ── Chat: handles become markdown links ──────────────────────────────────────


def test_chat_doc_handle_becomes_link(matter, document):
    text = resolve_handles_for_chat(f"See [doc:{document.id}] for terms.", matter)
    assert (
        text == f"See [Test Document](/case/documents/{document.id}/view/) for terms."
    )


def test_chat_hl_handle_becomes_link(matter, highlight):
    text = resolve_handles_for_chat(f"Per [hl:{highlight.id}].", matter)
    assert f"](/case/highlights/{highlight.id}/link/)" in text
    assert "[hl:" not in text


def test_chat_note_handle_left_alone(matter):
    # Notes are retired: a [note:ID] is no longer a handle.
    assert resolve_handles_for_chat("See [note:12].", matter) == "See [note:12]."


def test_chat_unknown_handle_omitted(matter):
    assert resolve_handles_for_chat("See [doc:999999].", matter) == "See ."


def test_chat_cross_matter_doc_omitted(matter, document, contact, practice_area):
    from apps.matters.models import Matter

    other = Matter.objects.create(
        name="Other", client=contact, practice_area=practice_area
    )
    assert resolve_handles_for_chat(f"[doc:{document.id}]", other) == ""


def test_chat_label_brackets_stripped(matter, document):
    document.name = "Exhibit [A] | Contract"
    document.save()
    text = resolve_handles_for_chat(f"[doc:{document.id}]", matter)
    assert text == f"[Exhibit A  Contract](/case/documents/{document.id}/view/)"


# ── Invented pseudo-handles stripped ─────────────────────────────────────────


def test_pseudo_fact_handle_stripped(matter):
    text = "C&B issued a 10-day notice [fact:2026-03-17]."
    assert resolve_handles_for_chat(text, matter) == "C&B issued a 10-day notice."


def test_pseudo_task_handle_stripped(matter):
    assert resolve_handles_for_chat("Done [task:12].", matter) == "Done."


def test_bracketed_prose_not_stripped(matter):
    text = "The [Fact Sheet] and [sic] remain."
    assert resolve_handles_for_chat(text, matter) == text
