"""The matter tools a session's agent can call, as an in-process MCP server.

The twelve read-only tools of the earlier agent loop (agent_tools.py:
search_materials, read_document, read_email_thread, read_matter_section,
the CourtListener research tools and so on) are reused as they are: their
provider-neutral specs become MCP tools and their executor runs each call
on a worker thread, since the handlers use the ORM synchronously. Two
tools are added for the new table, so a session can read earlier
sessions on the matter the way it reads archived conversations.

Tool names reach the model as ``mcp__kosmos__<name>``.
"""

import json

import anyio
from claude_agent_sdk import create_sdk_mcp_server, tool

from .access import has_financial_access, has_research_access
from .agent_tools import DEFAULT_BUDGET, build_agent_tools, make_agent_executor
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


def build_session_server(session, user):
    """The in-process MCP server for one turn, built for ``user``: the
    financial and research tools appear only with those permissions, as
    in the earlier loop. Returns (server_config, tool_names)."""
    specs = build_agent_tools(
        DEFAULT_BUDGET,
        include_financial=has_financial_access(user),
        include_research=has_research_access(user),
    )
    executor = make_agent_executor(
        session.matter, None, DEFAULT_BUDGET, on_event=None, user=user
    )
    tools = []
    for spec in specs:
        tools.append(_wrap(spec, executor.execute_one))
    tools.extend(_session_tools(session, user))
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
