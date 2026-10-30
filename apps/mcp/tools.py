"""The tools the remote MCP server offers Claude: one per service function
in apps/ai/api.py and apps/search/api.py, which own all access control,
ranking and formatting. This module only describes the tools (name,
description, JSON schema) and turns their results into text.

Reads cover every section of a matter (including its AI conversations,
ledger and trust position), invoices, the matter's hybrid keyword and
semantic material search, and the practice-wide search; writes are
narrow: create-only timeline facts, witnesses, tasks, time entries,
events and contacts, and marking a task complete (the one update, and a
reversible one). Money reads require the user's financial permission in
Kosmos.
"""

from dataclasses import dataclass
from typing import Callable

from apps.accounts.api_auth import ApiError
from apps.ai import api
from apps.search.api import search_practice

READ_TRUNCATE_CHARS = 40_000

MATTER_SECTIONS = list(api.SECTIONS)


class ToolError(Exception):
    """What the model is told when a tool cannot do what it was asked:
    the text travels back as an error result, not a protocol error."""


class InvalidArguments(Exception):
    """Arguments that do not fit the tool's schema: a protocol error."""


def _truncate(content):
    if len(content) <= READ_TRUNCATE_CHARS:
        return content
    total = len(content)
    return (
        content[:READ_TRUNCATE_CHARS]
        + f"\n\n[truncated at {READ_TRUNCATE_CHARS:,} characters; {total:,} total]"
    )


def _int(args, name, required=True):
    value = args.get(name)
    if value is None:
        if required:
            raise InvalidArguments(f"{name} is required.")
        return None
    if isinstance(value, bool):
        raise InvalidArguments(f"{name} must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise InvalidArguments(f"{name} must be an integer.")


def _str(args, name, required=True):
    value = args.get(name)
    if value is None or value == "":
        if required:
            raise InvalidArguments(f"{name} is required.")
        return None
    if not isinstance(value, str):
        raise InvalidArguments(f"{name} must be a string.")
    return value


def _list(args, name):
    value = args.get(name)
    if value is None:
        return None
    if not isinstance(value, list):
        raise InvalidArguments(f"{name} must be a list.")
    return value


def _number(args, name):
    value = args.get(name)
    if value is None:
        raise InvalidArguments(f"{name} is required.")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise InvalidArguments(f"{name} must be a number.")
    return value


def _bool(args, name):
    value = args.get(name)
    if value is None:
        return False
    if not isinstance(value, bool):
        raise InvalidArguments(f"{name} must be true or false.")
    return value


def _call(service, *args):
    """Run a service function, relaying its refusal to the model."""
    try:
        return service(*args)
    except ApiError as exc:
        raise ToolError(f"Kosmos API error ({exc.status}): {exc.message}")


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------


def find_matter(user, args):
    query = _str(args, "query")
    matters = _call(api.list_matters, user, query)
    if not matters:
        return f"No open matters match {query!r}."
    return "\n".join(f"- [id {m['id']}] {m['name']}" for m in matters)


def read_matter(user, args):
    result = _call(
        api.read_section, user, _int(args, "matter_id"), _str(args, "section")
    )
    return _truncate(result["text"])


def search_matter(user, args):
    body = {
        "query": _str(args, "query", required=False),
        "queries": _list(args, "queries"),
        "kinds": _list(args, "kinds"),
        "limit": _int(args, "limit", required=False) or 15,
    }
    result = _call(api.search_materials, user, _int(args, "matter_id"), body)
    hits = result["hits"]
    if not hits:
        return f"No materials match {result['queries']!r}."
    lines = []
    for hit in hits:
        bits = [hit["name"]]
        if hit.get("category"):
            bits.append(hit["category"])
        if hit.get("date"):
            bits.append(hit["date"])
        flags = []
        if hit.get("semantic"):
            flags.append("semantic")
        if hit.get("fuzzy"):
            flags.append("fuzzy")
        if hit.get("matched") and len(result["queries"]) > 1:
            flags.append("matched: " + "; ".join(hit["matched"]))
        line = f"- [{hit['handle']}] {' | '.join(bits)}"
        if flags:
            line += f" ({', '.join(flags)})"
        if hit.get("snippet"):
            line += f"\n  {hit['snippet']}"
        if hit.get("summary"):
            line += f"\n  Summary: {hit['summary']}"
        lines.append(line)
    if result.get("note"):
        lines.append(result["note"])
    return "\n".join(lines)


def search_kosmos(user, args):
    result = _call(
        search_practice, user, _str(args, "query"), _str(args, "scope", False) or "all"
    )
    return result["text"]


def read_document(user, args):
    doc = _call(api.read_document, user, _int(args, "document_id"))
    text = doc["text"] or f"(no extracted text; OCR status: {doc['ocr_status']})"
    return (
        f"# {doc['name']}\n"
        f"Matter: {doc['matter']}\n"
        f"Category: {doc['category']}, date: {doc['date'] or 'none'}\n\n"
        f"{_truncate(text)}"
    )


def read_email_thread(user, args):
    result = _call(
        api.read_email_thread, user, _int(args, "matter_id"), _str(args, "thread_id")
    )
    return _truncate(result["text"])


def read_conversation(user, args):
    result = _call(
        api.read_conversation,
        user,
        _int(args, "matter_id"),
        _int(args, "conversation_id"),
    )
    return (
        f"# {result['title']}\n"
        f"Matter: {result['matter']}\n"
        f"Mode: {result['kind']}, model: {result['llm']}\n\n"
        f"{_truncate(result['text'])}"
    )


def read_invoice(user, args):
    result = _call(api.read_invoice, user, _int(args, "invoice_id"))
    return f"Matter: {result['matter']}\n\n{_truncate(result['text'])}"


def add_fact(user, args):
    entry = {
        "description": _str(args, "description"),
        "date": _str(args, "date", False),
        "time": _str(args, "time", False),
        "importance": _int(args, "importance", False) or 4,
        "color": _str(args, "color", False),
        "highlights": _list(args, "highlight_ids") or [],
        "documents": _list(args, "document_ids") or [],
    }
    return _call(api.create_fact, user, _int(args, "matter_id"), entry)["message"]


def add_witness(user, args):
    entry = {
        "name": _str(args, "name"),
        "affiliation": _str(args, "affiliation", False),
        "alignment": _str(args, "alignment", False) or "neutral",
        "knowledge": _str(args, "knowledge", False),
        "phone": _str(args, "phone", False),
        "email": _str(args, "email", False),
        "address": _str(args, "address", False),
        "importance": _int(args, "importance", False) or 4,
    }
    payload, _created = _call(api.create_witness, user, _int(args, "matter_id"), entry)
    return payload["message"]


def add_task(user, args):
    entry = {
        "description": _str(args, "description"),
        "matter_id": _int(args, "matter_id", False),
        "due": _str(args, "due", False),
        "importance": _int(args, "importance", False) or 4,
    }
    result = _call(api.create_task, user, entry)
    return f"{result['message']} [{result['matter']}]"


def add_time_entry(user, args):
    entry = {
        "actions": _str(args, "actions"),
        "hours": _number(args, "hours"),
        "date": _str(args, "date", False),
        "category": _str(args, "category", False),
    }
    return _call(api.create_time_entry, user, _int(args, "matter_id"), entry)["message"]


def add_event(user, args):
    entry = {
        "description": _str(args, "description"),
        "date": _str(args, "date"),
        "matter_id": _int(args, "matter_id", False),
        "end_date": _str(args, "end_date", False),
        "start_time": _str(args, "start_time", False),
        "end_time": _str(args, "end_time", False),
        "party": _str(args, "party", False),
        "location": _str(args, "location", False),
        "event_type": _str(args, "event_type", False),
        "details": _str(args, "details", False),
        "assigned_to_me": _bool(args, "assigned_to_me"),
    }
    return _call(api.create_event, user, entry)["message"]


def complete_task(user, args):
    return _call(api.complete_task, user, _int(args, "task_id"))["message"]


def add_contact(user, args):
    entry = {
        "name": _str(args, "name"),
        "company": _str(args, "company", False),
        "email": _str(args, "email", False),
        "phone": _str(args, "phone", False),
        "address": _str(args, "address", False),
        "notes": _str(args, "notes", False),
        "matter_id": _int(args, "matter_id", False),
        "role": _str(args, "role", False),
        "group": _str(args, "group", False),
    }
    payload, _created = _call(api.create_contact, user, entry)
    return payload["message"]


# ---------------------------------------------------------------------------
# Descriptions and schemas: what Claude reads to decide what to call
# ---------------------------------------------------------------------------


def _schema(properties, required=()):
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


_MATTER_ID = {
    "type": "integer",
    "description": "The matter's id, from find_matter or search_kosmos.",
}
_IMPORTANCE = {
    "type": "integer",
    "minimum": 1,
    "maximum": 7,
    "description": "1-7 (4 = normal).",
}
_ID_LIST = {"type": "array", "items": {"type": "integer"}}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    run: Callable
    read_only: bool = True

    def listing(self):
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "readOnlyHint": self.read_only,
                "destructiveHint": False,
                "openWorldHint": False,
            },
        }


TOOLS = [
    Tool(
        "find_matter",
        "Find open Kosmos matters by name (case-insensitive contains match). "
        "Use this once to resolve a matter name (e.g. from the project "
        "instructions) to its matter_id, then pass that id to the other "
        "matter tools. Returns each match as its id and full name.",
        _schema({"query": {"type": "string"}}, ["query"]),
        find_matter,
    ),
    Tool(
        "read_matter",
        "Read one section of a matter's record (resolve the id with "
        "find_matter first).\n\n"
        "Sections: overview, contacts (the parties with [contact:ID] "
        "handles, and the groups and roles add_contact may use), rates "
        "(billing setup and hourly "
        "rates), activity (time entries, expenses, and flat fees with "
        "category coding), events, tasks (capped at 20, with [task:ID] "
        "handles for complete_task), proceedings, "
        "settlement, documents (metadata manifest; use read_document for a "
        "document's full text), highlights (excerpts with [hl:ID] handles "
        "usable as add_fact sources), timeline (the facts chronology), "
        "witnesses, emails (thread manifest, most recent activity first; "
        "use read_email_thread for a full thread, and search_matter with "
        'kinds=["email"] for older threads past the truncation point), '
        "conversations (manifest of earlier AI chats on the matter with "
        "[conv:ID] handles; use read_conversation for a transcript), ledger "
        "(sent invoices, payments, credits, running balance, unbilled work, "
        "unsent invoices, open payment requests; [inv:ID] handles feed "
        "read_invoice), trust (the client's trust balance, trust available, "
        "and transaction history).\n\n"
        "ledger and trust require the user's financial permission in Kosmos. "
        "Start with overview; then read only the sections the question needs.",
        _schema(
            {
                "matter_id": _MATTER_ID,
                "section": {"type": "string", "enum": MATTER_SECTIONS},
            },
            ["matter_id", "section"],
        ),
        read_matter,
    ),
    Tool(
        "search_matter",
        "Hybrid search across one matter's materials: documents (OCR text), "
        "synced emails, highlights, and timeline facts. Matches by meaning as "
        "well as by words (semantic neighbors are merged with the keyword "
        "hits).\n\n"
        'Keyword side: words are stemmed and ANDed; use "quoted phrases" '
        "for exact wording, OR between alternatives, and -word to exclude. "
        "Prefer queries with 2 to 4 differently phrased variants (synonyms, "
        "terms of art, statute numbers): one call runs them all and merges "
        "the ranked hits. When nothing matches, near-miss titles come back as "
        "fuzzy hits. kinds restricts to any of: document, email, highlight, "
        "fact. limit is at most 40.\n\n"
        "Each hit carries a snippet and the handle to read the full item "
        "(doc: read_document, thread: read_email_thread; hl: and fact: are "
        "already in the highlights and timeline sections). Hits marked "
        "semantic were found by meaning alone, so the words themselves may "
        "not appear in the text.",
        _schema(
            {
                "matter_id": _MATTER_ID,
                "query": {"type": "string"},
                "queries": {"type": "array", "items": {"type": "string"}},
                "kinds": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["document", "email", "highlight", "fact"],
                    },
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 40},
            },
            ["matter_id"],
        ),
        search_matter,
    ),
    Tool(
        "search_kosmos",
        "Search the whole practice the way the Kosmos search page does: "
        "matters (name, status note, description), proceedings (fuzzy case "
        'number: "2024cv12345" finds "2024-CV-12345"), contacts (name, '
        "company, email, phone, notes), and intakes (name, email, phone). An "
        "all-digit query matches client reference ids and phone numbers "
        "exactly.\n\n"
        "scope is one of: all, matters, proceedings, contacts, intakes. "
        "Results carry [matter:ID], [proceeding:ID], [contact:ID], and "
        "[intake:ID] handles; matter ids feed the read_matter tools (open "
        "matters only). Use find_matter instead when you only need a "
        "matter's id by name.",
        _schema(
            {
                "query": {"type": "string"},
                "scope": {
                    "type": "string",
                    "enum": ["all", "matters", "proceedings", "contacts", "intakes"],
                },
            },
            ["query"],
        ),
        search_kosmos,
    ),
    Tool(
        "read_document",
        "Read one document's extracted text, by the [doc:ID] id shown in the "
        "documents section. Returns the OCR/extracted text (scans with no "
        "text yet report their status instead). Very large documents are "
        "truncated, with an explicit marker saying so.",
        _schema({"document_id": {"type": "integer"}}, ["document_id"]),
        read_document,
    ),
    Tool(
        "read_email_thread",
        "Read one synced email thread in full, by the thread id shown in the "
        "emails section. Messages are oldest-first and include any extracted "
        "attachment text. Very large threads are truncated, with an explicit "
        "marker saying so.",
        _schema(
            {"matter_id": _MATTER_ID, "thread_id": {"type": "string"}},
            ["matter_id", "thread_id"],
        ),
        read_email_thread,
    ),
    Tool(
        "read_conversation",
        "Read the full transcript of one earlier AI conversation on a matter, "
        "by the [conv:ID] id shown in the conversations section. Useful when "
        "the section's summary suggests the conversation already analyzed "
        "the question. Messages are oldest-first, each labelled with the "
        "speaker. Very large transcripts are truncated, with an explicit "
        "marker saying so.",
        _schema(
            {"matter_id": _MATTER_ID, "conversation_id": {"type": "integer"}},
            ["matter_id", "conversation_id"],
        ),
        read_conversation,
    ),
    Tool(
        "read_invoice",
        "Read one invoice, by the [inv:ID] id shown in the ledger section: "
        "totals, discount, balance remaining, and every time, expense, and "
        "flat-fee line item. Requires the user's financial permission in "
        "Kosmos. Only for billing questions.",
        _schema({"invoice_id": {"type": "integer"}}, ["invoice_id"]),
        read_invoice,
    ),
    Tool(
        "add_fact",
        "Add one fact to a matter's timeline. Creates immediately; only call "
        "on the user's explicit direction, and read the timeline section "
        "first to avoid duplicating an existing fact.\n\n"
        "description is a terse noun-phrase headline (aim for 20-60 "
        "characters; hard cap 150). date/time are ISO (YYYY-MM-DD, HH:MM); "
        "importance is 1-7 (4 = normal). Source the fact with highlight_ids "
        "([hl:ID] from the highlights section, preferred) or document_ids "
        "([doc:ID]); never cite both for the same source. Ids outside the "
        "matter are silently dropped.",
        _schema(
            {
                "matter_id": _MATTER_ID,
                "description": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM"},
                "importance": _IMPORTANCE,
                "color": {"type": "string"},
                "highlight_ids": _ID_LIST,
                "document_ids": _ID_LIST,
            },
            ["matter_id", "description"],
        ),
        add_fact,
        read_only=False,
    ),
    Tool(
        "add_witness",
        "Add one witness to a matter. Creates immediately; only call on the "
        "user's explicit direction. A same-named witness already in the "
        "matter is reported instead of duplicated.\n\n"
        "affiliation is the party or faction they belong to; alignment is "
        "friendly, neutral, or hostile as seen from our client's side; "
        "knowledge summarizes what they can testify to. Never guess contact "
        "details (phone, email, address); leave them out unless the record "
        "states them. importance is 1-7 (4 = normal).",
        _schema(
            {
                "matter_id": _MATTER_ID,
                "name": {"type": "string"},
                "affiliation": {"type": "string"},
                "alignment": {
                    "type": "string",
                    "enum": ["friendly", "neutral", "hostile"],
                },
                "knowledge": {"type": "string"},
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "address": {"type": "string"},
                "importance": _IMPORTANCE,
            },
            ["matter_id", "name"],
        ),
        add_witness,
        read_only=False,
    ),
    Tool(
        "add_task",
        "Add one task, assigned to the user's own account. Creates "
        "immediately; only call on the user's explicit direction. due is an "
        "ISO date (YYYY-MM-DD); importance is 1-7 (4 = normal). Pass "
        "matter_id to file the task under a matter, or omit it for a general "
        "Admin task.",
        _schema(
            {
                "description": {"type": "string"},
                "matter_id": _MATTER_ID,
                "due": {"type": "string", "description": "YYYY-MM-DD"},
                "importance": _IMPORTANCE,
            },
            ["description"],
        ),
        add_task,
        read_only=False,
    ),
    Tool(
        "add_time_entry",
        "Log one time entry on an hourly matter, as the user, at the user's "
        "rate for that matter (Kosmos sets the rate; never pass one). "
        "Creates immediately, unbilled and marked as needing approval, "
        "which the user or an admin gives on the Activity tab; only call on "
        "the user's explicit direction.\n\n"
        "actions is the billing narrative as it should appear on the "
        "invoice (write it in full; abbreviation codes are not expanded). "
        "hours is decimal, 0.1 to 99.9, rounded to a tenth. date is ISO "
        "(YYYY-MM-DD), today if omitted. category is one of the matter's "
        "activity categories by name (the activity section shows them in "
        "brackets); leave it out when unsure.",
        _schema(
            {
                "matter_id": _MATTER_ID,
                "actions": {"type": "string"},
                "hours": {"type": "number", "minimum": 0.1, "maximum": 99.9},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "category": {"type": "string"},
            },
            ["matter_id", "actions", "hours"],
        ),
        add_time_entry,
        read_only=False,
    ),
    Tool(
        "add_event",
        "Add one calendar event. Creates immediately; only call on the "
        "user's explicit direction, and read the events section first to "
        "avoid duplicating one.\n\n"
        "Pass matter_id to put the event on a matter, or omit it for a "
        "firm-wide event. description is 4-255 characters. date is ISO "
        "(YYYY-MM-DD); end_date only for an event over several days. "
        "start_time/end_time are HH:MM (24h); a start with no end runs an "
        "hour; omit both for an all-day event. party is who it is with "
        "(50 characters); location is the place; event_type is Zoom, "
        "Virtual, Phone, or In-person; details is free text (dial-in, "
        "agenda). The event goes on the firm's calendar (everyone's) "
        "unless assigned_to_me is true, which puts it on the user's own.",
        _schema(
            {
                "description": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "matter_id": _MATTER_ID,
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                "start_time": {"type": "string", "description": "HH:MM"},
                "end_time": {"type": "string", "description": "HH:MM"},
                "party": {"type": "string"},
                "location": {"type": "string"},
                "event_type": {
                    "type": "string",
                    "enum": ["Zoom", "Virtual", "Phone", "In-person"],
                },
                "details": {"type": "string"},
                "assigned_to_me": {"type": "boolean"},
            },
            ["description", "date"],
        ),
        add_event,
        read_only=False,
    ),
    Tool(
        "complete_task",
        "Mark one task complete, by the [task:ID] id shown in the tasks "
        "section. Applies immediately; only call on the user's explicit "
        "direction. A task already complete is reported, not changed; a "
        "task with an unfinished checklist is refused. Reversible in "
        "Kosmos.",
        _schema({"task_id": {"type": "integer"}}, ["task_id"]),
        complete_task,
        read_only=False,
    ),
    Tool(
        "add_contact",
        "Add one contact to the firm's address book, and optionally put it "
        "on a matter. Creates immediately; only call on the user's explicit "
        "direction. A same-named contact already in the address book is "
        "reported instead of duplicated (and still put on the matter when "
        "asked).\n\n"
        "name is 2-50 characters. Never guess contact details (company, "
        "email, phone, address); leave them out unless the record states "
        "them. phone is a 10-digit US number. notes is a short remark. To "
        "put the contact on a matter pass matter_id with role and group, "
        "both by name from the matter's contacts section (roles such as "
        "Counsel, Adversary, Judge, Expert - Testifying; groups are the "
        "matter's sides, such as Adversary, Court, Other). A wrong role or "
        "group is refused with the list to choose from.",
        _schema(
            {
                "name": {"type": "string"},
                "company": {"type": "string"},
                "email": {"type": "string"},
                "phone": {"type": "string"},
                "address": {"type": "string"},
                "notes": {"type": "string"},
                "matter_id": _MATTER_ID,
                "role": {"type": "string"},
                "group": {"type": "string"},
            },
            ["name"],
        ),
        add_contact,
        read_only=False,
    ),
]

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}

INSTRUCTIONS = (
    "Kosmos is this law firm's practice management system; these tools act "
    "as the signed-in user and see what that user may see. Resolve a matter "
    "by name once with find_matter (or search_kosmos for anything else in "
    "the practice), then pass its matter_id to read_matter, starting with "
    "the overview section, and to search_matter. The add_* tools create "
    "records immediately, and complete_task changes one: call them only "
    "when the user asks for the record."
)
