"""The matter tools a session's agent can call, as an in-process MCP server.

The twelve read-only tools of the earlier agent loop (agent_tools.py:
search_materials, read_document, read_email_thread, read_matter_section,
the CourtListener research tools and so on) are reused as they are: their
provider-neutral specs become MCP tools and their executor runs each call
on a worker thread, since the handlers use the ORM synchronously. Two
tools are added for the new table, so a session can read earlier
sessions on the matter the way it reads archived conversations, one for
the files, search_files, which sees inside PDFs and documents where the
harness's Grep cannot, and one write tool, save_caselaw, for a user who
may research.

Tool names reach the model as ``mcp__kosmos__<name>``.
"""

import json

import anyio
from claude_agent_sdk import create_sdk_mcp_server, tool

from apps.case.services import search_folder_text

from .access import has_financial_access, has_research_access
from .agent_tools import (
    DEFAULT_BUDGET,
    build_agent_tools,
    courtlistener_configured,
    make_agent_executor,
)
from .caselaw_save import save_authority
from .models import Session

SERVER_NAME = "kosmos"
SESSION_READ_CAP = 60_000


def tool_name(name: str) -> str:
    return f"mcp__{SERVER_NAME}__{name}"


def _text_result(text: str, is_error: bool = False) -> dict:
    result = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["is_error"] = True
    return result


def _session_tools(session, user):
    """list_sessions and read_session: the matter's other sessions."""

    @tool(
        "list_sessions",
        "Earlier Claude sessions on this matter (id, title, date, who started "
        "it, message count), newest first. Read one with read_session.",
        {},
    )
    async def list_sessions(args):
        def run():
            rows = (
                Session.objects.filter(matter=session.matter)
                .exclude(pk=session.pk)
                .select_related("user")
                .order_by("-created_at")[:50]
            )
            return [
                {
                    "session_id": s.id,
                    "title": s.display_title,
                    "date": s.created_at.date().isoformat(),
                    "started_by": s.user.get_full_name() if s.user else "",
                    "messages": s.messages.count(),
                }
                for s in rows
            ]

        rows = await anyio.to_thread.run_sync(run)
        return _text_result(json.dumps(rows, indent=1))

    @tool(
        "read_session",
        "The prompts and answers of one earlier session on this matter, by "
        "session_id from list_sessions.",
        {"session_id": int},
    )
    async def read_session(args):
        def run():
            other = (
                Session.objects.filter(
                    matter=session.matter, pk=args.get("session_id") or 0
                )
                .exclude(pk=session.pk)
                .first()
            )
            if other is None:
                return "No such session on this matter.", True
            parts = []
            for m in other.messages.select_related("user"):
                who = (
                    (m.user.get_full_name() if m.user else "User")
                    if m.role == "user"
                    else "Claude"
                )
                parts.append(f"### {who} ({m.created_at:%Y-%m-%d %H:%M})\n{m.content}")
            text = f"# {other.display_title}\n\n" + "\n\n".join(parts)
            if len(text) > SESSION_READ_CAP:
                text = text[:SESSION_READ_CAP] + "\n\n[truncated]"
            return text, False

        text, is_error = await anyio.to_thread.run_sync(run)
        return _text_result(text, is_error)

    return [list_sessions, read_session]


def _research_tools(session, user):
    """save_caselaw: the write half of the research tools, for a user
    who may research (the search and read tools come from agent_tools)."""

    @tool(
        "save_caselaw",
        "Save an opinion you read in this session to the matter's case law "
        "library, with the proposition it is cited for (one sentence). Only "
        "when the user asks to save; never a case you did not read here.",
        {
            "type": "object",
            "properties": {
                "cluster_id": {
                    "type": "integer",
                    "description": "The CourtListener cluster id from the research tools.",
                },
                "proposition": {
                    "type": "string",
                    "description": "The rule or holding the case is cited for.",
                },
                "court": {
                    "type": "string",
                    "description": "The court's display name as the search hit showed it.",
                },
            },
            "required": ["cluster_id", "proposition"],
        },
    )
    async def save_caselaw(args):
        def run():
            try:
                cluster_id = int(args.get("cluster_id") or 0)
            except (TypeError, ValueError):
                cluster_id = 0
            if not cluster_id:
                return "cluster_id is required.", True
            case_law = save_authority(
                session.matter,
                cluster_id,
                args.get("proposition"),
                args.get("court"),
                user,
            )
            if case_law is None:
                return (
                    f"Cluster {cluster_id} could not be fetched from CourtListener.",
                    True,
                )
            cite = f", {case_law.citation}" if case_law.citation else ""
            return f"Saved to case law: {case_law.case_name}{cite}", False

        text, is_error = await anyio.to_thread.run_sync(run)
        return _text_result(text, is_error)

    return [save_caselaw]


def _file_tools(folder):
    """search_files: the text inside the folder's documents, which the
    harness's Grep cannot see."""

    @tool(
        "search_files",
        "Search inside the matter's files for a word or phrase: PDFs (their "
        "text layer), ODT and DOCX documents and plain text. Grep reads bytes "
        "and cannot see inside a PDF or a document; use this for anything in "
        "the record. Returns the matching lines with the file and, for a PDF, "
        "the page. Case-insensitive; literal unless regex is true. One call "
        "searches the whole matter folder, which is fast; give path (a "
        "subfolder such as Record) only to narrow a search with too many hits.",
        {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The word, phrase or regular expression.",
                },
                "path": {
                    "type": "string",
                    "description": "A subfolder of the matter folder to search; the whole folder when empty.",
                },
                "regex": {
                    "type": "boolean",
                    "description": "Treat pattern as a regular expression.",
                },
            },
            "required": ["pattern"],
        },
    )
    async def search_files(args):
        pattern = str(args.get("pattern") or "").strip()
        if not pattern:
            return _text_result("pattern is required.", True)
        if folder is None:
            return _text_result(
                "No folder is linked to this matter, so there are no files to search.",
                True,
            )
        text = await anyio.to_thread.run_sync(
            lambda: search_folder_text(
                folder,
                pattern,
                subpath=str(args.get("path") or "").strip().strip("/"),
                regex=bool(args.get("regex")),
            )
        )
        return _text_result(text)

    return [search_files]


def build_session_tools(session, user, folder=None):
    """The tools of one turn, built for ``user``: the financial and
    research tools appear only with those permissions, as in the
    earlier loop. ``folder`` is the linked matter folder, or None."""
    specs = build_agent_tools(
        DEFAULT_BUDGET,
        include_financial=has_financial_access(user),
        include_research=has_research_access(user),
    )
    executor = make_agent_executor(
        session.matter, None, DEFAULT_BUDGET, on_event=None, user=user
    )
    tools = [_wrap(spec, executor.execute_one) for spec in specs]
    tools.extend(_file_tools(folder))
    tools.extend(_session_tools(session, user))
    if has_research_access(user) and courtlistener_configured():
        tools.extend(_research_tools(session, user))
    return tools


def build_session_server(session, user, folder=None):
    """The in-process MCP server for one turn. Returns (server_config,
    tool_names), the names as the model sees them."""
    tools = build_session_tools(session, user, folder)
    server = create_sdk_mcp_server(SERVER_NAME, version="1.0.0", tools=tools)
    return server, [tool_name(t.name) for t in tools]


def _wrap(spec: dict, execute_one):
    """One agent_tools spec as an MCP tool whose call runs the executor's
    handler on a worker thread."""
    name = spec["name"]

    async def call(args):
        outcome = await anyio.to_thread.run_sync(
            execute_one, {"id": name, "name": name, "input": args or {}}
        )
        return _text_result(outcome.get("content") or "", bool(outcome.get("is_error")))

    return tool(name, spec["description"], spec["input_schema"])(call)
