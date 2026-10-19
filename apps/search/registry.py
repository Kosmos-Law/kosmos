"""Kinds of thing the firm-wide search finds beyond its own (matters,
proceedings, contacts, intakes). An app that holds searchable rows
registers a kind at start-up; the search page and the MCP search then
offer its scope, run it through the same watson index, and render its
section, without the search app importing the app that owns the rows.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SearchKind:
    key: str  # the scope name, e.g. "notes"
    label: str
    model: type  # a watson-registered model
    order: int
    visible: Callable  # (obj, user, accessible_matter_ids) -> bool
    line: Callable  # obj -> one manifest line for the MCP search
    template: str  # the results section; rendered with ``rows``
    enabled: Callable = lambda: True  # a firm feature switch, when there is one


_KINDS: dict[str, SearchKind] = {}


def register_kind(kind):
    _KINDS[kind.key] = kind
    return kind


def kinds():
    return sorted(
        (kind for kind in _KINDS.values() if kind.enabled()),
        key=lambda kind: kind.order,
    )
