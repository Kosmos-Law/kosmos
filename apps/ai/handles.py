"""Translation of raw context handles the AI leaks into its output.

Context items carry [doc:ID] and [hl:ID] handles so the AI can
cite and target them (SOURCE_LINKING teaches markdown links; the write
protocols consume ids). Models still sometimes emit the raw handles in
prose, which are meaningless to a human. These helpers are the safety
net, applied after the response arrives:

- resolve_handles_for_chat(): handle -> markdown link (same targets
  SOURCE_LINKING teaches), so the chat message reads and clicks.

Out-of-scope or nonexistent ids are omitted entirely — a hallucinated
handle must not become a link.
"""

import re

from django.db.models import Q

from apps.case.models import Document, Highlight

HANDLE_RE = re.compile(r"\[(doc|hl):(\d+)\]")

# Invented handle-style citations to records that are not citable
# (observed live: "[fact:2026-03-17]"). Only documents and highlights
# are citation targets; these are stripped along with any space before
# them. The colon requirement keeps ordinary bracketed prose ("[Fact
# Sheet]") safe.
PSEUDO_HANDLE_RE = re.compile(
    r"\s*\[(?:facts?|tasks?|events?|time|entry|entries|conv|conversations?|emails?)"
    r":[^\]]*\]",
    re.IGNORECASE,
)


def _clean_label(text, fallback):
    """Strip the characters that would break a markdown link."""
    label = re.sub(r"[\[\]|]", "", str(text or "")).replace("\n", " ").strip()
    return label[:80] or fallback


def _resolve(kind, item_id, matter):
    """Return (label, url) for an in-scope handle, or None."""
    if kind == "doc":
        doc = Document.objects.filter(id=item_id, matter=matter).first()
        if doc:
            return (
                _clean_label(doc.name, f"Document {doc.id}"),
                f"/case/documents/{doc.id}/view/",
            )
    elif kind == "hl":
        hl = (
            Highlight.objects.filter(id=item_id)
            .filter(Q(document__matter=matter) | Q(caselaw__matter=matter))
            .first()
        )
        if hl:
            return (
                _clean_label(hl.citation, f"Highlight {hl.id}"),
                f"/case/highlights/{hl.id}/link/",
            )
    return None


def resolve_handles_for_chat(text, matter):
    """Replace raw handles with markdown links; omit unresolvable ones."""

    def sub(match):
        resolved = _resolve(match.group(1), int(match.group(2)), matter)
        if resolved is None:
            return ""
        label, url = resolved
        return f"[{label}]({url})"

    text = PSEUDO_HANDLE_RE.sub("", text)
    return HANDLE_RE.sub(sub, text)
