"""
Tools for the agentic chat mode.

The agent turn (agent.py) gives the model a small orientation prompt and
these read-only tools instead of a preloaded matter context; the model
opens what it needs. Three pieces live here:

- ``build_agent_tools`` returns provider-neutral tool specs
  ({"name", "description", "input_schema"}) that both provider loops
  translate (Anthropic takes them as is; Gemini gets FunctionDeclarations).
- ``make_agent_executor`` returns ``execute_batch(calls) -> outcomes``:
  the handlers, a per-turn budget (calls and characters read), a dedupe
  cache so an exact repeat of a call is served free and flagged, and the
  step events the live status box renders.
- ``run_tool_batch`` runs one model turn's calls concurrently while
  preserving their order, which is what both loops need to answer the
  turn with results in block order.

Every tool result is a JSON object; failures come back as {"error": ...}
so the model can react instead of the run dying. Writes stay on the
fenced-block path (tasks.finalize_response), shared with the classic chat.
"""

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from django.db import connections
from django.db.models import Q

from apps.case.services import semantic_entries

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentBudget:
    """Per-turn limits the executor enforces and the prompt announces."""

    max_tool_calls: int = 40
    max_chars: int = 600_000
    default_read_chars: int = 60_000
    max_read_chars: int = 150_000
    max_turns: int = 30
    parallel_workers: int = 4


DEFAULT_BUDGET = AgentBudget()

SEARCH_KINDS = ("document", "email", "highlight", "fact")
SEARCH_DEFAULT_LIMIT = 15
SEARCH_MAX_LIMIT = 40
SEARCH_MAX_QUERIES = 5
# word_similarity floor for the typo-tolerant fallback.
SEARCH_FUZZY_FLOOR = 0.4
SNIPPET_CHARS = 300
SECTION_CAP = 150_000

# A search whose hits were mostly returned by an earlier search this turn
# earns a note; the research loop showed rephrase-looping burns budget.
OVERLAP_SHARE = 0.7

BUDGET_EXHAUSTED = (
    "Tool budget exhausted ({calls} calls, {chars:,} characters read this "
    "turn). Answer now from what you have read."
)
READ_BUDGET_EXHAUSTED = (
    "Reading budget exhausted ({chars:,} characters this turn). Answer now "
    "from what you have read."
)
REPEAT_NOTE = (
    "You already made this exact call this turn; the same result is "
    "returned and not charged. Change the input instead of repeating it."
)


def _read_params(extra: dict | None = None) -> dict:
    """The offset/max_chars pair every text read accepts."""
    props = {
        "offset": {
            "type": "integer",
            "description": (
                "Character offset to start from, for reading a long text in "
                "parts. Use next_offset from the previous part. Defaults to 0."
            ),
        },
        "max_chars": {
            "type": "integer",
            "description": (
                "Characters to return in this part. Defaults to the standard "
                "part size; larger values are capped."
            ),
        },
    }
    props.update(extra or {})
    return props


# Tools and sections behind a permission. The specs offered to the model and
# the executor's handlers are both built for the requesting user, so a tool
# the user may not use is neither advertised nor run.
FINANCIAL_TOOLS = ("read_invoice",)
# Never offered to the agent, whoever asks: read_invoice covers billing
# questions for the users who may ask them.
AGENT_WITHHELD_SECTIONS = ("ledger", "trust")
FINANCIAL_REFUSAL = (
    "Billing records are not available to this user (no Financial permission)."
)


def agent_sections(include_financial: bool) -> list[str]:
    """The matter sections read_matter_section serves to this user."""
    from apps.ai.api import FINANCIAL_SECTIONS, SECTIONS

    return [
        name
        for name in SECTIONS
        if name not in AGENT_WITHHELD_SECTIONS
        and (include_financial or name not in FINANCIAL_SECTIONS)
    ]


def build_agent_tools(
    budget: AgentBudget = DEFAULT_BUDGET,
    include_financial: bool = False,
) -> list[dict]:
    """Provider-neutral tool specs for one agent turn, for one user:
    read_invoice and the rates section need the Financial permission."""
    section_enum = [
        name
        for name in (
            "overview",
            "contacts",
            "rates",
            "activity",
            "events",
            "tasks",
            "proceedings",
            "settlement",
            "documents",
            "highlights",
            "timeline",
            "witnesses",
            "emails",
        )
        if include_financial or name != "rates"
    ]
    rates_section = "rates, " if include_financial else ""
    tools = [
        {
            "name": "search_materials",
            "description": (
                "Hybrid search across this matter's materials: documents "
                "(OCR text), synced emails, highlights and timeline facts. Matches by meaning as well as "
                "by words (semantic neighbors are merged with the keyword "
                "hits). Keyword side: words are stemmed and ANDed; "
                'use "quoted phrases" for exact wording, OR between '
                "alternatives, and -word to exclude. Prefer `queries` with 2 "
                "to 4 differently phrased variants (synonyms, terms of art, "
                "statute numbers): one call runs them all, merges the ranked "
                "hits, and flags which variants matched. When nothing "
                "matches, near-miss titles come back as fuzzy hits. Each hit "
                "carries a snippet and the handle to read the full item; "
                "document hits also carry an AI summary when one "
                "exists, useful for triage before reading."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A single search (prefer queries).",
                    },
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Two to four differently phrased searches, run "
                            "together and merged."
                        ),
                    },
                    "kinds": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(SEARCH_KINDS)},
                        "description": (
                            "Restrict to these kinds. Defaults to all kinds."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            f"Maximum hits, default {SEARCH_DEFAULT_LIMIT}, "
                            f"at most {SEARCH_MAX_LIMIT}."
                        ),
                    },
                },
            },
        },
        {
            "name": "read_document",
            "description": (
                "The extracted text of a document in the index ([doc:ID]). "
                f"Long documents come in parts of {budget.default_read_chars:,} "
                "characters; the result reports total_chars and next_offset."
            ),
            "input_schema": {
                "type": "object",
                "properties": _read_params(
                    {"doc_id": {"type": "integer", "description": "Document id."}}
                ),
                "required": ["doc_id"],
            },
        },
        {
            "name": "read_email_thread",
            "description": (
                "A synced email thread in full ([thread:ID] in the index), "
                "oldest message first, with attachment names."
            ),
            "input_schema": {
                "type": "object",
                "properties": _read_params(
                    {
                        "thread_id": {
                            "type": "string",
                            "description": "Thread id from the index or a search hit.",
                        }
                    }
                ),
                "required": ["thread_id"],
            },
        },
        {
            "name": "read_conversation",
            "description": (
                "The transcript of an earlier AI conversation on this matter "
                "([conv:ID]); useful when the index summary suggests it "
                "already analyzed the question."
            ),
            "input_schema": {
                "type": "object",
                "properties": _read_params(
                    {
                        "conversation_id": {
                            "type": "integer",
                            "description": "Conversation id.",
                        }
                    }
                ),
                "required": ["conversation_id"],
            },
        },
        {
            "name": "read_invoice",
            "description": (
                "One invoice on this matter ([inv:ID]) with its line items "
                "and balance. Only for billing questions."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "integer", "description": "Invoice id."}
                },
                "required": ["invoice_id"],
            },
        },
        {
            "name": "read_matter_section",
            "description": (
                "A structured section of the matter record as text: "
                f"overview, contacts, {rates_section}"
                "activity (time and expenses), "
                "events, tasks, proceedings, settlement, documents (the "
                "manifest), highlights, timeline, witnesses, emails (the "
                "thread manifest). The overview, contacts, witnesses and "
                "proceedings are already in your orientation; read the others "
                "when the question needs them."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": section_enum,
                        "description": "Section name.",
                    }
                },
                "required": ["section"],
            },
        },
    ]
    if include_financial:
        return tools
    return [tool for tool in tools if tool["name"] not in FINANCIAL_TOOLS]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _k(n: int) -> str:
    """41k / 812 style size for step labels."""
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.0f}k"
    return str(n)


def _snippet(text: str, query: str, width: int = SNIPPET_CHARS) -> str:
    """A window of ``text`` centred on the first query term it contains."""
    text = (text or "").replace("\n", " ").strip()
    if not text:
        return ""
    lower = text.lower()
    pos = -1
    for term in query.lower().split():
        pos = lower.find(term)
        if pos >= 0:
            break
    if pos < 0:
        return text[:width] + ("..." if len(text) > width else "")
    start = max(0, pos - width // 2)
    end = min(len(text), start + width)
    piece = text[start:end]
    if start > 0:
        piece = "..." + piece
    if end < len(text):
        piece += "..."
    return piece


PENDING_LABELS = {
    "search_materials": 'Searching "{query}"...',
    "read_document": "Reading document {doc_id}...",
    "read_email_thread": "Reading email thread {thread_id}...",
    "read_conversation": "Reading conversation {conversation_id}...",
    "read_invoice": "Reading invoice {invoice_id}...",
    "read_matter_section": "Reading the {section} section...",
}


def _pending_label(name: str, tool_input: dict) -> str:
    """The status line while a call runs, before its result names it."""
    template = PENDING_LABELS.get(name)
    if not template:
        return f"Running {name}..."
    try:
        return template.format(
            **{k: str(v)[:60] for k, v in (tool_input or {}).items()}
        )
    except (KeyError, IndexError):
        return f"Running {name}..."


def _canonical(name: str, tool_input: dict) -> str:
    return name + ":" + json.dumps(tool_input or {}, sort_keys=True, default=str)


def run_tool_batch(calls: list[dict], execute_one, max_workers: int) -> list[dict]:
    """Run one turn's calls, concurrently when there are several.

    Results come back in the calls' order. A handler that raises yields an
    error outcome for that call; nothing escapes. The inline path (one
    call, or a worker cap of one) is also what tests that stub
    threading.Thread rely on.
    """
    if len(calls) <= 1 or max_workers <= 1:
        return [execute_one(call) for call in calls]

    def worker(call):
        try:
            return execute_one(call)
        finally:
            # ORM use opens a connection per pool thread; release it.
            connections.close_all()

    with ThreadPoolExecutor(max_workers=min(max_workers, len(calls))) as pool:
        return list(pool.map(worker, calls))


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


def make_agent_executor(
    matter,
    conversation,
    budget: AgentBudget = DEFAULT_BUDGET,
    on_event=None,
    is_cancelled=None,
    user=None,
):
    """Build ``execute_batch(calls) -> outcomes`` for one agent turn.

    The executor works for ``user``: read_invoice and the rates section
    need their Financial permission. With no user, they are not available.

    ``calls`` are ``{"id", "name", "input"}``; outcomes are ``{"id",
    "name", "content": json string, "is_error"}`` in the same order.
    ``on_event(step)`` fires when a call starts (``pending`` True) and
    again on the same dict when it finishes, so the live log shows one
    row per tool that fills in. ``execute_batch.set_turn(n)`` tags the
    steps with the model turn; ``execute_batch.usage()`` reports the
    counters for the status payload.
    """
    from apps.case.models import Document, Fact, Highlight
    from apps.invoicing.invoices.models import Invoice
    from apps.mail.ai import format_email_thread, thread_subject

    from .access import has_financial_access
    from .models import Conversation

    include_financial = has_financial_access(user)

    lock = threading.Lock()
    state = {"calls": 0, "chars": 0, "n": 0, "turn": 0}
    results_cache: dict[str, dict] = {}
    seen_hits: set[tuple[str, str]] = set()

    def _budget():
        return {
            "calls_left": max(0, budget.max_tool_calls - state["calls"]),
            "chars_left": max(0, budget.max_chars - state["chars"]),
        }

    def _charge_chars(n: int):
        with lock:
            state["chars"] += n

    def _chars_left():
        return max(0, budget.max_chars - state["chars"])

    def _slice(text: str, tool_input: dict) -> tuple[dict, int]:
        """Apply offset/max_chars to ``text``; returns (fields, chars)."""
        total = len(text)
        try:
            offset = max(0, int(tool_input.get("offset") or 0))
        except (TypeError, ValueError):
            offset = 0
        try:
            requested = int(tool_input.get("max_chars") or budget.default_read_chars)
        except (TypeError, ValueError):
            requested = budget.default_read_chars
        size = max(1, min(requested, budget.max_read_chars, _chars_left()))
        chunk = text[offset : offset + size]
        end = offset + len(chunk)
        fields = {
            "text": chunk,
            "total_chars": total,
            "offset": offset,
            "next_offset": end if end < total else None,
            "truncated": end < total,
        }
        return fields, len(chunk)

    def _part_detail(fields: dict) -> str:
        """The outcome half of a read: size, or the slice read."""
        total = fields["total_chars"]
        if fields["offset"] == 0 and not fields["truncated"]:
            return f"{_k(total)} chars"
        start = fields["offset"]
        end = start + len(fields["text"])
        return f"chars {start:,} to {end:,} of {_k(total)}"

    def _part_label(verb: str, name: str, fields: dict) -> str:
        return f"{verb} *{name}* ({_part_detail(fields)})"

    # -- handlers: return (payload, step_fields) ---------------------------

    def _search_scopes(kinds):
        """kind -> (ContentType, scoped pk queryset) for the watson table."""
        from django.contrib.contenttypes.models import ContentType

        from apps.mail.models import Email

        scopes = {}
        if "document" in kinds:
            scopes["document"] = (
                ContentType.objects.get_for_model(Document),
                Document.objects.filter(matter=matter).exclude(ai_context="never"),
            )
        if "highlight" in kinds:
            scopes["highlight"] = (
                ContentType.objects.get_for_model(Highlight),
                Highlight.objects.filter(document__matter=matter),
            )
        if "fact" in kinds:
            scopes["fact"] = (
                ContentType.objects.get_for_model(Fact),
                Fact.objects.filter(matter=matter),
            )
        if "email" in kinds:
            scopes["email"] = (
                ContentType.objects.get_for_model(Email),
                Email.objects.filter(matter=matter).exclude(ai_context="never"),
            )
        return scopes

    def _scope_filter(scopes):
        # Join on the text object_id: watson always writes it, while
        # object_id_int stays NULL for BigAutoField primary keys.
        scope_q = Q(pk__in=[])
        for content_type, id_qs in scopes.values():
            ids = [str(pk) for pk in id_qs.values_list("pk", flat=True)]
            scope_q |= Q(content_type=content_type, object_id__in=ids)
        return scope_q

    def _fulltext_entries(query, scopes, cap):
        """websearch_to_tsquery over the watson index, ranked, scoped."""
        from django.db.models import FloatField
        from django.db.models.expressions import RawSQL
        from watson.models import SearchEntry

        return list(
            SearchEntry.objects.filter(_scope_filter(scopes))
            .extra(
                where=[
                    "watson_searchentry.search_tsv @@ "
                    "websearch_to_tsquery('pg_catalog.english', %s)"
                ],
                params=[query],
            )
            .annotate(
                rank=RawSQL(
                    "ts_rank_cd(watson_searchentry.search_tsv, "
                    "websearch_to_tsquery('pg_catalog.english', %s))",
                    (query,),
                    output_field=FloatField(),
                )
            )
            .order_by("-rank")[:cap]
        )

    def _fuzzy_entries(query, scopes, cap):
        """Typo-tolerant fallback: near-miss titles and descriptions by
        trigram word similarity (pg_trgm), when no variant matched."""
        from django.contrib.postgres.search import TrigramWordSimilarity
        from django.db.models.functions import Greatest
        from watson.models import SearchEntry

        return list(
            SearchEntry.objects.filter(_scope_filter(scopes))
            .annotate(
                rank=Greatest(
                    TrigramWordSimilarity(query, "title"),
                    TrigramWordSimilarity(query, "description"),
                )
            )
            .filter(rank__gt=SEARCH_FUZZY_FLOOR)
            .order_by("-rank")[:cap]
        )

    def _entry_hits(entries, scopes, query):
        """SearchEntry rows -> hit dicts (emails grouped by thread)."""
        from apps.mail.models import Email

        def _oid(entry):
            if entry.object_id_int is not None:
                return entry.object_id_int
            try:
                return int(entry.object_id)
            except (TypeError, ValueError):
                return None

        by_ct = {}
        for entry in entries:
            by_ct.setdefault(entry.content_type_id, []).append(entry)
        objects = {}
        loaders = {
            Document: lambda ids: Document.objects.filter(pk__in=ids).defer(
                "ocr_text", "search_vector"
            ),
            Highlight: lambda ids: Highlight.objects.filter(pk__in=ids).select_related(
                "document"
            ),
            Fact: lambda ids: Fact.objects.filter(pk__in=ids),
            Email: lambda ids: Email.objects.filter(pk__in=ids),
        }
        cts = {ct.id: ct for ct, _ in scopes.values()}
        for ct_id, ct_entries in by_ct.items():
            content_type = cts.get(ct_id)
            model = content_type.model_class() if content_type else None
            loader = loaders.get(model)
            if loader is None:
                continue
            ids = [oid for oid in (_oid(e) for e in ct_entries) if oid is not None]
            for obj in loader(ids):
                objects[(ct_id, obj.pk)] = obj

        hits = []
        for entry in entries:
            obj = objects.get((entry.content_type_id, _oid(entry)))
            if obj is None:
                continue
            snippet = _snippet(entry.content or entry.description or "", query)
            rank = float(getattr(entry, "rank", 0) or 0)
            if isinstance(obj, Document):
                hit = {
                    "kind": "document",
                    "id": obj.id,
                    "handle": f"doc:{obj.id}",
                    "name": obj.name,
                    "category": obj.category,
                    "date": str(obj.date) if obj.date else None,
                    "snippet": snippet,
                    "rank": rank,
                }
                if obj.summary:
                    hit["summary"] = obj.summary
                hits.append(hit)
            elif isinstance(obj, Highlight):
                hit = {
                    "kind": "highlight",
                    "id": obj.id,
                    "handle": f"hl:{obj.id}",
                    "name": obj.citation,
                    "category": obj.color,
                    "date": None,
                    "snippet": _snippet(obj.text, query),
                    "rank": rank,
                }
                hit["document_id"] = obj.document_id
                hit["date"] = str(obj.document.date) if obj.document.date else None
                hits.append(hit)
            elif isinstance(obj, Fact):
                hits.append(
                    {
                        "kind": "fact",
                        "id": obj.id,
                        "handle": f"fact:{obj.id}",
                        "name": obj.description or "",
                        "category": "timeline",
                        "date": str(obj.date) if obj.date else None,
                        "snippet": obj.description or "",
                        "rank": rank,
                    }
                )
            else:  # Email -> one hit per thread
                key = obj.thread_id or obj.gmail_id
                hits.append(
                    {
                        "kind": "email",
                        "id": key,
                        "handle": f"thread:{key}",
                        "name": obj.subject or "(no subject)",
                        "category": "Email thread",
                        "date": f"{obj.date:%Y-%m-%d}" if obj.date else None,
                        "snippet": snippet,
                        "rank": rank,
                    }
                )
        return hits

    def _semantic_hits(rows):
        """Semantic rows -> hit dicts shaped like the keyword hits."""
        from apps.mail.models import Email

        loaders = {
            "document": lambda ids: Document.objects.filter(pk__in=ids).defer(
                "ocr_text", "search_vector"
            ),
            "email": lambda ids: Email.objects.filter(pk__in=ids),
            "highlight": lambda ids: Highlight.objects.filter(
                pk__in=ids
            ).select_related("document"),
            "fact": lambda ids: Fact.objects.filter(pk__in=ids),
        }
        by_kind = {}
        for row in rows:
            by_kind.setdefault(row["kind"], []).append(row["object_id"])
        objects = {}
        for kind, ids in by_kind.items():
            for obj in loaders[kind](ids):
                objects[(kind, obj.pk)] = obj

        hits = []
        for row in rows:
            obj = objects.get((row["kind"], row["object_id"]))
            if obj is None:
                continue
            kind = row["kind"]
            snippet = _snippet(row["text"], row["query"])
            base = {
                "kind": kind,
                "matched": [row["query"]],
                "similarity": row["similarity"],
                "snippet": snippet,
            }
            if kind == "document":
                base.update(
                    id=obj.id,
                    handle=f"doc:{obj.id}",
                    name=obj.name,
                    category=obj.category,
                    date=str(obj.date) if obj.date else None,
                )
                if obj.summary:
                    base["summary"] = obj.summary
            elif kind == "email":
                key = obj.thread_id or obj.gmail_id
                base.update(
                    id=key,
                    handle=f"thread:{key}",
                    name=obj.subject or "(no subject)",
                    category="Email thread",
                    date=f"{obj.date:%Y-%m-%d}" if obj.date else None,
                )
            elif kind == "highlight":
                base.update(
                    id=obj.id,
                    handle=f"hl:{obj.id}",
                    name=obj.citation,
                    category=obj.color,
                    date=None,
                )
                base["document_id"] = obj.document_id
            else:  # fact
                base.update(
                    id=obj.id,
                    handle=f"fact:{obj.id}",
                    name=obj.description or "",
                    category="timeline",
                    date=str(obj.date) if obj.date else None,
                )
            hits.append(base)
        return hits

    def _search(tool_input):
        raw = tool_input.get("queries") or []
        if isinstance(raw, str):
            raw = [raw]
        single = str(tool_input.get("query") or "").strip()
        queries = []
        for candidate in ([single] if single else []) + [str(x) for x in raw]:
            candidate = candidate.strip()
            if candidate and candidate.lower() not in [q.lower() for q in queries]:
                queries.append(candidate)
        queries = queries[:SEARCH_MAX_QUERIES]
        if not queries:
            return {"error": "Provide query or queries."}, {}
        kinds = tool_input.get("kinds") or list(SEARCH_KINDS)
        kinds = [k for k in kinds if k in SEARCH_KINDS] or list(SEARCH_KINDS)
        try:
            limit = int(tool_input.get("limit") or SEARCH_DEFAULT_LIMIT)
        except (TypeError, ValueError):
            limit = SEARCH_DEFAULT_LIMIT
        limit = max(1, min(limit, SEARCH_MAX_LIMIT))

        scopes = _search_scopes(kinds)

        merged = {}
        score = {}

        def _fuse(hit_lists, source):
            for hits_list in hit_lists:
                for position, hit in enumerate(hits_list):
                    key = hit["handle"]
                    kept = merged.get(key)
                    if kept is None:
                        hit["matched"] = list(hit.get("matched") or [])
                        hit["_sources"] = {source}
                        merged[key] = hit
                        kept = hit
                    else:
                        kept["_sources"].add(source)
                    for matched_query in hit.get("matched") or []:
                        if matched_query not in kept["matched"]:
                            kept["matched"].append(matched_query)
                    # Reciprocal rank fusion across every list.
                    score[key] = score.get(key, 0.0) + 1.0 / (60 + position)

        keyword_lists = []
        for query in queries:
            hits_list = _entry_hits(
                _fulltext_entries(query, scopes, limit * 2), scopes, query
            )
            for hit in hits_list:
                hit["matched"] = [query]
                hit.pop("rank", None)
            keyword_lists.append(hits_list)
        _fuse(keyword_lists, "keyword")

        semantic_lists = [
            _semantic_hits(rows)
            for rows in semantic_entries(queries, matter, kinds, limit)
        ]
        _fuse(semantic_lists, "semantic")

        fuzzy = False
        if not merged:
            fuzzy = True
            fuzzy_lists = []
            for query in queries:
                hits_list = _entry_hits(
                    _fuzzy_entries(query, scopes, limit), scopes, query
                )
                for hit in hits_list:
                    hit["matched"] = [query]
                    hit["fuzzy"] = True
                    hit.pop("rank", None)
                fuzzy_lists.append(hits_list)
            _fuse(fuzzy_lists, "fuzzy")

        hits = sorted(merged.values(), key=lambda h: -score[h["handle"]])[:limit]
        for hit in hits:
            sources = hit.pop("_sources", set())
            if sources == {"semantic"}:
                # Found by meaning alone: worth the agent knowing the
                # words themselves may not appear in the text.
                hit["semantic"] = True

        seen_count = 0
        with lock:
            for hit in hits:
                key = (hit["kind"], str(hit["id"]))
                hit["seen"] = key in seen_hits
                seen_count += hit["seen"]
                seen_hits.add(key)
        payload = {"queries": queries, "hits": hits, "total": len(hits)}
        if fuzzy:
            payload["note"] = (
                "No exact matches for any variant; these are near matches "
                "by title similarity. Check the names before relying on them."
            )
        elif len(hits) >= 3 and seen_count / len(hits) >= OVERLAP_SHARE:
            payload["note"] = (
                "Most of these hits came back from an earlier search this "
                "turn. Use different terms, or read what you already found."
            )
        more = f" and {len(queries) - 1} more" if len(queries) > 1 else ""
        seen = f", {seen_count} seen before" if seen_count else ""
        fuzz = ", near matches" if fuzzy else ""
        label = (
            f'Searched "{queries[0]}"{more} ({len(hits)} hit'
            f"{'s' if len(hits) != 1 else ''}{seen}{fuzz})"
        )
        return payload, {
            "label": label,
            "title": f'Searched "{queries[0]}"{more}',
            "detail": f"{len(hits)} hits{seen}{fuzz}",
            "query": queries[0],
            "queries": queries,
            "kinds": kinds,
            "hits": len(hits),
            "seen": seen_count,
            "chars": 0,
        }

    def _read_document(tool_input):
        doc = Document.objects.filter(
            matter=matter, pk=tool_input.get("doc_id") or 0
        ).first()
        if doc is None:
            return {"error": "No such document on this matter."}, {}
        if doc.ai_context == "never":
            return {"error": f"Document {doc.id} is excluded from AI use."}, {}
        if doc.ocr_status not in ("completed", "extracted") or not doc.ocr_text:
            return {
                "error": (
                    f"Document {doc.id} has no extracted text "
                    f"(OCR status {doc.ocr_status})."
                )
            }, {}
        fields, chars = _slice(doc.ocr_text, tool_input)
        payload = {
            "doc_id": doc.id,
            "name": doc.name,
            "category": doc.category,
            "date": str(doc.date) if doc.date else None,
            **fields,
        }
        if doc.description:
            payload["description"] = doc.description
        if doc.summary:
            payload["summary"] = doc.summary
        return payload, {
            "label": _part_label("Read", doc.name, fields),
            "title": f"Read *{doc.name}*",
            "detail": _part_detail(fields),
            "kind": "document",
            "id": doc.id,
            "name": doc.name,
            "chars": chars,
            "total_chars": fields["total_chars"],
        }

    def _read_email_thread(tool_input):
        thread_id = str(tool_input.get("thread_id") or "").strip()
        if not thread_id:
            return {"error": "thread_id is required."}, {}
        emails = list(
            matter.emails.filter(thread_id=thread_id)
            .exclude(ai_context="never")
            .dedup()
            .prefetch_related("attachment_files")
        )
        if not emails:
            emails = list(
                matter.emails.filter(gmail_id=thread_id)
                .exclude(ai_context="never")
                .dedup()
                .prefetch_related("attachment_files")
            )
        if not emails:
            return {"error": "No such email thread on this matter."}, {}
        emails.sort(key=lambda e: e.date or e.created_at)
        subject = thread_subject(emails)
        fields, chars = _slice(format_email_thread(emails), tool_input)
        payload = {
            "thread_id": thread_id,
            "subject": subject,
            "messages": len(emails),
            **fields,
        }
        return payload, {
            "label": _part_label("Read thread", subject, fields),
            "title": f"Read thread *{subject}*",
            "detail": _part_detail(fields),
            "kind": "email",
            "id": thread_id,
            "name": subject,
            "chars": chars,
            "total_chars": fields["total_chars"],
        }

    def _read_conversation(tool_input):
        conv = (
            Conversation.objects.filter(
                matter=matter, pk=tool_input.get("conversation_id") or 0
            )
            .exclude(pk=getattr(conversation, "pk", None) or 0)
            .exclude(ai_context="never")
            .first()
        )
        if conv is None:
            return {"error": "No such earlier conversation on this matter."}, {}
        lines = [f"Conversation: {conv.title or 'Untitled'}"]
        for msg in conv.messages.select_related("user").order_by("created_at"):
            if msg.role == "user":
                who = msg.user.get_full_name() if msg.user else "User"
            else:
                who = "Assistant"
            lines.append(f"**{who}:** {msg.content}")
        fields, chars = _slice("\n\n".join(lines), tool_input)
        name = conv.title or "Untitled"
        payload = {"conversation_id": conv.id, "title": name, **fields}
        return payload, {
            "label": _part_label("Read conversation", name, fields),
            "title": f"Read conversation *{name}*",
            "detail": _part_detail(fields),
            "kind": "conversation",
            "id": conv.id,
            "name": name,
            "chars": chars,
            "total_chars": fields["total_chars"],
        }

    def _read_invoice(tool_input):
        from .context import format_invoice

        invoice = Invoice.objects.filter(
            matter=matter, pk=tool_input.get("invoice_id") or 0
        ).first()
        if invoice is None:
            return {"error": "No such invoice on this matter."}, {}
        text = format_invoice(invoice)
        name = f"Invoice #{invoice.id}"
        return {"invoice_id": invoice.id, "text": text}, {
            "label": f"Read *{name}*",
            "title": f"Read *{name}*",
            "detail": f"{_k(len(text))} chars",
            "kind": "invoice",
            "id": invoice.id,
            "name": name,
            "chars": len(text),
            "total_chars": len(text),
        }

    def _read_section(tool_input):
        from apps.ai.api import FINANCIAL_SECTIONS, SECTIONS

        allowed = agent_sections(include_financial)
        section = str(tool_input.get("section") or "")
        if (
            section in FINANCIAL_SECTIONS
            and section not in AGENT_WITHHELD_SECTIONS
            and not include_financial
        ):
            return {"error": FINANCIAL_REFUSAL}, {}
        if section not in allowed:
            return {
                "error": f"Unknown section. Valid sections: {', '.join(allowed)}."
            }, {}
        text = SECTIONS[section](matter)[:SECTION_CAP]
        return {"section": section, "text": text}, {
            "label": f"Read the {section} section ({_k(len(text))} chars)",
            "title": f"Read the {section} section",
            "detail": f"{_k(len(text))} chars",
            "kind": "section",
            "id": section,
            "name": section,
            "chars": len(text),
            "total_chars": len(text),
        }

    handlers = {
        "search_materials": _search,
        "read_document": _read_document,
        "read_email_thread": _read_email_thread,
        "read_conversation": _read_conversation,
        "read_invoice": _read_invoice,
        "read_matter_section": _read_section,
    }

    def _refusal(message):
        return lambda tool_input: ({"error": message}, {})

    # A model can still name a tool it was not offered (from an earlier
    # turn's habit, or a prompt that asks for it): refuse here too.
    if not include_financial:
        for tool_name in FINANCIAL_TOOLS:
            handlers[tool_name] = _refusal(FINANCIAL_REFUSAL)

    # -- dispatch -----------------------------------------------------------

    def _outcome(call, payload, is_error):
        payload = dict(payload)
        payload["budget"] = _budget()
        return {
            "id": call.get("id"),
            "name": call.get("name"),
            "content": json.dumps(payload, default=str),
            "is_error": bool(is_error),
        }

    def _emit(step):
        if on_event:
            try:
                on_event(step)
            except Exception:
                logger.exception("Agent step event failed")

    def execute_one(call):
        name = call.get("name") or ""
        tool_input = call.get("input") or {}
        handler = handlers.get(name)
        with lock:
            state["n"] += 1
            n = state["n"]
        step = {
            "type": "tool",
            "tool": name,
            "n": n,
            "turn": state["turn"],
            "ts": time.time(),
            "seconds": 0.0,
            "label": _pending_label(name, tool_input),
            "title": _pending_label(name, tool_input),
            "detail": "",
            "pending": True,
            "error": None,
            "repeat": False,
        }
        started = time.time()

        def finish(payload, step_fields, is_error=False):
            step.update(step_fields)
            step["pending"] = False
            step["seconds"] = round(time.time() - started, 2)
            if is_error:
                step["error"] = payload.get("error", "error")
                step["label"] = f"{name}: {step['error']}"
            _emit(step)
            return _outcome(call, payload, is_error)

        if handler is None:
            _emit(step)
            return finish({"error": f"Unknown tool {name!r}."}, {}, True)
        if is_cancelled and is_cancelled():
            _emit(step)
            return finish({"error": "Request cancelled."}, {}, True)

        key = _canonical(name, tool_input)
        with lock:
            cached = results_cache.get(key)
            if cached is None:
                if state["calls"] >= budget.max_tool_calls:
                    exhausted = True
                else:
                    exhausted = False
                    state["calls"] += 1
        if cached is not None:
            step["repeat"] = True
            _emit(step)
            payload = dict(cached["payload"])
            payload["note"] = REPEAT_NOTE
            fields = dict(cached["step"])
            fields["label"] = fields.get("label", name) + " (repeat, not charged)"
            detail = fields.get("detail") or ""
            fields["detail"] = (
                f"{detail}, repeat, not charged" if detail else "repeat, not charged"
            )
            fields["chars"] = 0
            return finish(payload, fields, cached["is_error"])
        if exhausted:
            _emit(step)
            return finish(
                {
                    "error": BUDGET_EXHAUSTED.format(
                        calls=budget.max_tool_calls, chars=state["chars"]
                    )
                },
                {},
                True,
            )
        if name != "search_materials" and _chars_left() <= 0:
            _emit(step)
            return finish(
                {"error": READ_BUDGET_EXHAUSTED.format(chars=state["chars"])},
                {},
                True,
            )

        _emit(step)
        try:
            payload, step_fields = handler(tool_input)
        except Exception:
            logger.exception("Agent tool %s failed", name)
            payload, step_fields = (
                {"error": f"Tool {name} failed; try differently."},
                {},
            )
        is_error = "error" in payload
        if not is_error:
            _charge_chars(int(step_fields.get("chars") or 0))
            with lock:
                results_cache[key] = {
                    "payload": payload,
                    "step": step_fields,
                    "is_error": False,
                }
        return finish(payload, step_fields, is_error)

    def execute_batch(calls):
        return run_tool_batch(calls, execute_one, budget.parallel_workers)

    def set_turn(n):
        state["turn"] = n

    def usage():
        return {
            "tool_calls": state["calls"],
            "tool_calls_max": budget.max_tool_calls,
            "chars_read": state["chars"],
            "chars_read_max": budget.max_chars,
        }

    execute_batch.set_turn = set_turn
    execute_batch.usage = usage
    execute_batch.execute_one = execute_one
    return execute_batch
