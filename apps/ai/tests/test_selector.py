from unittest.mock import patch

import pytest

from apps.ai.selector import (
    ManifestItem,
    _fallback_by_importance,
    _parse_selector_response,
    select_context,
)

pytestmark = pytest.mark.django_db


def test_parses_selected_items():
    assert _parse_selector_response(
        '{"selected": [{"type": "document", "id": 3}, {"type": "email", "id": "7"}]}'
    ) == [("document", 3), ("email", 7)]


def test_retired_note_types_are_ignored():
    assert (
        _parse_selector_response(
            '{"selected": [{"type": "note", "id": 7}, {"type": "library", "id": 8}]}'
        )
        == []
    )


def test_null_selected_means_nothing_selected():
    assert _parse_selector_response('{"selected": null}') == []


def test_strips_markdown_fences():
    assert _parse_selector_response('```json\n{"selected": []}\n```') == []


def _mk(item_type, item_id, words=100, importance=4):
    return ManifestItem(
        item_type=item_type,
        item_id=item_id,
        name=f"{item_type}-{item_id}",
        category="",
        date=None,
        description="",
        word_count=words,
        importance=importance,
    )


class TestSelection:
    def test_small_matter_short_circuits(self):
        items = [_mk("document", 1)]
        content_map = {("document", 1): "doc text"}
        with patch("apps.ai.selector.complete") as send:
            selected, unselected = select_context(items, content_map, "q", 10_000)
        assert not send.called
        assert selected == ["doc text"]

    def test_invoices_bypass_short_circuit(self):
        items = [_mk("document", 1), _mk("invoice", 2)]
        content_map = {("document", 1): "doc text", ("invoice", 2): "inv text"}
        with patch(
            "apps.ai.selector.complete",
            return_value=('{"selected": [{"type": "invoice", "id": 2}]}', 1, 1),
        ) as send:
            selected, unselected = select_context(items, content_map, "q", 10_000)
        assert send.called
        assert selected == ["inv text"]
        assert [i.item_id for i in unselected] == [1]

    def test_fallback_never_picks_invoices(self):
        items = [_mk("invoice", 1, importance=7), _mk("document", 2, importance=1)]
        content_map = {("invoice", 1): "inv", ("document", 2): "doc"}
        keys = _fallback_by_importance(items, content_map, 10_000)
        assert ("invoice", 1) not in keys
        assert ("document", 2) in keys
