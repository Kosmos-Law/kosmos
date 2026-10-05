"""Tests for per-conversation context reuse (assemble_matter_context_with_selection)."""

import pytest
from django.core.cache import cache as default_cache

from apps.case.ai import selector
from apps.case.ai.context import (
    assemble_matter_context_with_selection,
    context_reuse_key,
)
from apps.case.ai.models import Conversation
from apps.case.ai.status import status_cache
from apps.notes.models import Note

pytestmark = pytest.mark.django_db


@pytest.fixture
def conversation(matter):
    return Conversation.objects.create(matter=matter, title="Chat", llm="claude-opus")


@pytest.fixture
def manifest_counter(monkeypatch):
    calls = {"n": 0}

    def counting_build_manifest(*args, **kwargs):
        calls["n"] += 1
        return [], {}

    monkeypatch.setattr(selector, "build_manifest", counting_build_manifest)
    status_cache.clear()
    default_cache.clear()
    return calls


def assemble(matter, conversation, user, message):
    return assemble_matter_context_with_selection(
        matter,
        user_message=message,
        llm="claude-opus",
        user=user,
        conversation=conversation,
    )


def test_follow_up_reuses_context(user, matter, conversation, manifest_counter):
    first = assemble(matter, conversation, user, "analyze service of process")
    second = assemble(matter, conversation, user, "now save that to a note")
    assert manifest_counter["n"] == 1
    assert second == first


def test_reuse_entry_is_cross_process(user, matter, conversation, manifest_counter):
    """The follow-up's run thread lands in whichever worker took the
    request, so the entry has to live in the shared ai_status store (the
    database table), not the per-process default cache (2026-08-17 for
    the run status; the context entry had stayed behind)."""
    assemble(matter, conversation, user, "question")
    key = context_reuse_key(conversation.id)
    assert status_cache.get(key) is not None
    assert default_cache.get(key) is None


def test_material_change_rebuilds(user, matter, conversation, manifest_counter):
    assemble(matter, conversation, user, "question one")
    Note.objects.create(matter=matter, title="AI conclusion", content="text")
    assemble(matter, conversation, user, "question two")
    assert manifest_counter["n"] == 2


def test_conversations_do_not_share(user, matter, conversation, manifest_counter):
    other = Conversation.objects.create(matter=matter, title="Other", llm="claude-opus")
    assemble(matter, conversation, user, "question")
    assemble(matter, other, user, "question")
    assert manifest_counter["n"] == 2


def test_no_conversation_never_caches(user, matter, manifest_counter):
    assemble(matter, None, user, "nightly summary pass")
    assemble(matter, None, user, "nightly summary pass")
    assert manifest_counter["n"] == 2


def test_assembly_emits_activity_lines(user, matter, conversation, manifest_counter):
    lines = []
    assemble_matter_context_with_selection(
        matter,
        user_message="q",
        llm="claude-opus",
        user=user,
        conversation=conversation,
        on_activity=lines.append,
    )
    assert any(line.startswith("Case file gathered") for line in lines)
    assert "No additional materials to catalogue" in lines
    assert any(line.startswith("Context assembled") for line in lines)

    # Second call reuses the cached context and says so.
    lines.clear()
    assemble_matter_context_with_selection(
        matter,
        user_message="q2",
        llm="claude-opus",
        user=user,
        conversation=conversation,
        on_activity=lines.append,
    )
    assert lines == ["Context reused from the previous turn (case file unchanged)"]
