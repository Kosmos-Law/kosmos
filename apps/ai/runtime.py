"""One session turn, run by the Claude Agent SDK.

``run_turn(message_id)`` fills one pending assistant message: it starts
the harness (the Claude Code binary) in the matter's folder with the
session's model, the session prompt and the Kosmos tools as an
in-process MCP server, feeds it the prompt, and records what comes back.
The transcript is the harness's (resumed by ``sdk_session_id`` on the
next turn); Kosmos keeps the prompt, the answer, the readable trail and
the cost.

Live progress goes to the ``ai_status`` cache under the message's key,
which the page polls; a cancel flag in the same cache interrupts the
turn. The sessions service (``manage.py run_sessions``) is what calls
this, on a thread per turn.
"""

import asyncio
import logging
import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.llm.status import status_cache
from apps.settings.ai import ANTHROPIC, api_key

from .models import SessionMessage

logger = logging.getLogger(__name__)

LIVE_TTL = 180
FINAL_TTL = 600
SERVICE_KEY = "ai_sessions_service_seen"
SERVICE_TTL = 90
BUILTIN_TOOLS = ["Read", "Grep", "Glob"]
TEXT_CAP = 400_000


def live_key(message_id):
    return f"ai_session_turn_{message_id}"


def cancel_key(message_id):
    return f"ai_session_cancel_{message_id}"


def service_alive() -> bool:
    return bool(status_cache.get(SERVICE_KEY))


def service_heartbeat():
    status_cache.set(SERVICE_KEY, time.time(), SERVICE_TTL)


def request_cancel(message_id):
    status_cache.set(cancel_key(message_id), True, LIVE_TTL)


def live_state(message_id):
    return status_cache.get(live_key(message_id))


def _step_summary(name: str, tool_input: dict) -> str:
    """One readable line per tool call for the trail."""
    short = name.split("__")[-1]
    if short == "Read":
        return f"Read {Path(str(tool_input.get('file_path', ''))).name}"
    if short == "Grep":
        where = tool_input.get("path") or ""
        return f"Grep '{tool_input.get('pattern', '')}'" + (
            f" in {Path(where).name}" if where else ""
        )
    if short == "Glob":
        return f"Glob {tool_input.get('pattern', '')}"
    if short == "search_materials":
        queries = tool_input.get("queries") or [tool_input.get("query", "")]
        return "Search: " + "; ".join(str(q) for q in queries if q)
    if short == "read_document":
        return f"Read document {tool_input.get('document_id', '')}"
    if short == "read_matter_section":
        return f"Read matter {tool_input.get('section', '')}"
    if short == "read_email_thread":
        return "Read email thread"
    if short == "search_caselaw":
        return f"Search case law: {tool_input.get('query', '')}"
    if short == "read_opinion":
        return f"Read opinion {tool_input.get('cluster_id', '')}"
    if short == "save_caselaw":
        return f"Save case law {tool_input.get('cluster_id', '')}"
    if short == "lookup_citation":
        return f"Look up {tool_input.get('citation', '')}"
    if short == "search_in_opinions":
        return f"Search opinions for '{tool_input.get('query', tool_input.get('pattern', ''))}'"
    if short == "read_caselaw":
        return f"Read saved case {tool_input.get('caselaw_id', '')}"
    if short == "read_invoice":
        return f"Read invoice {tool_input.get('invoice_id', '')}"
    if short == "read_session":
        return f"Read session {tool_input.get('session_id', '')}"
    if short == "list_sessions":
        return "List earlier sessions"
    if short == "read_conversation":
        return f"Read conversation {tool_input.get('conversation_id', '')}"
    return short


class Turn:
    """The state of one running turn, flushed to the cache as it goes."""

    def __init__(self, message):
        self.message = message
        self.session = message.session
        self.text = ""
        self.trail = []
        self.started = time.monotonic()
        self.usage = {}
        self.cost = None
        self.sdk_session_id = ""
        self.cancelled = False
        self.prompt = ""
        self.result = None
        self._last_flush = 0.0

    def state(self, status="running"):
        return {
            "status": status,
            "text": self.text[-20_000:],
            "trail": self.trail[-60:],
            "steps": len(self.trail),
            "elapsed": int(time.monotonic() - self.started),
            "usage": self.usage,
            "cost": self.cost,
        }

    def flush(self, force=False):
        now = time.monotonic()
        if force or now - self._last_flush > 0.5:
            status_cache.set(live_key(self.message.id), self.state(), LIVE_TTL)
            self._last_flush = now

    def on_message(self, msg):
        from claude_agent_sdk import (
            AssistantMessage,
            ResultMessage,
            SystemMessage,
            TextBlock,
            ToolResultBlock,
            ToolUseBlock,
            UserMessage,
        )

        if isinstance(msg, SystemMessage):
            if msg.subtype == "init":
                self.sdk_session_id = msg.data.get("session_id") or self.sdk_session_id
        elif isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    self.text = (self.text + "\n\n" + block.text).strip()[-TEXT_CAP:]
                elif isinstance(block, ToolUseBlock):
                    self.trail.append(
                        {
                            "id": block.id,
                            "name": block.name,
                            "summary": _step_summary(block.name, block.input or {}),
                            "pending": True,
                            "error": False,
                        }
                    )
            if msg.usage:
                self.usage = _merge_usage(self.usage, msg.usage)
        elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    for step in self.trail:
                        if step["id"] == block.tool_use_id:
                            step["pending"] = False
                            step["error"] = bool(block.is_error)
        elif isinstance(msg, ResultMessage):
            self.sdk_session_id = msg.session_id or self.sdk_session_id
            if msg.usage:
                self.usage = _merge_usage({}, msg.usage)
            self.cost = msg.total_cost_usd
            self.result = msg


def _merge_usage(total: dict, usage: dict) -> dict:
    out = dict(total)
    for key in (
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ):
        if key in usage and usage[key] is not None:
            out[key] = usage[key]
    return out


def _options(session, user, folder_path, linked, server, tool_names):
    from claude_agent_sdk import ClaudeAgentOptions

    from .session_prompt import build_session_system

    key = api_key(ANTHROPIC)
    env = {
        "ANTHROPIC_API_KEY": key or "",
        "CLAUDE_CONFIG_DIR": str(settings.SESSIONS_HOME),
        "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    return ClaudeAgentOptions(
        cwd=str(folder_path),
        model=session.model,
        system_prompt=build_session_system(
            session, user, folder_path if linked else None
        ),
        tools=list(BUILTIN_TOOLS),
        allowed_tools=list(BUILTIN_TOOLS) + list(tool_names),
        permission_mode="dontAsk",
        mcp_servers={server["name"]: server},
        strict_mcp_config=True,
        setting_sources=[],
        resume=session.sdk_session_id or None,
        max_turns=settings.SESSIONS_MAX_TURNS,
        max_budget_usd=settings.SESSIONS_MAX_BUDGET_USD,
        effort="high",
        env=env,
        stderr=lambda line: logger.debug("claude: %s", line.rstrip()),
    )


def _working_directory(session) -> tuple[Path, bool]:
    """The linked matter folder and True, or a scratch directory of the
    session's own and False when none is linked (the prompt then says
    there are no files)."""
    from apps.case.services import matter_folder

    folder = matter_folder(session.matter)
    if folder is not None and folder.exists:
        return folder.absolute_path(), True
    scratch = Path(settings.SESSIONS_SCRATCH) / str(session.id)
    scratch.mkdir(parents=True, exist_ok=True)
    return scratch, False


async def _run(turn: Turn, options):
    from claude_agent_sdk import ClaudeSDKClient

    prompt = turn.prompt
    # The cache is the database; the ORM refuses to run on the event
    # loop's thread, so each write and the cancel check go to a thread.
    cancel = cancel_key(turn.message.id)
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            turn.on_message(msg)
            await asyncio.to_thread(turn.flush)
            if await asyncio.to_thread(status_cache.get, cancel):
                turn.cancelled = True
                await client.interrupt()


def run_turn(message_id: int):
    """Fill one pending assistant message. The caller owns the thread's
    database connection (the service closes it after each turn)."""
    message = SessionMessage.objects.select_related("session__matter").get(
        pk=message_id
    )
    if message.status != "pending":
        return message
    session = message.session
    user = message.user or session.user
    prompt_row = (
        session.messages.filter(role="user", id__lt=message.id).order_by("-id").first()
    )
    message.status = "running"
    message.started_at = timezone.now()
    message.save(update_fields=["status", "started_at", "updated_at"])

    turn = Turn(message)
    turn.prompt = prompt_row.content if prompt_row else ""
    turn.flush(force=True)
    try:
        from .session_tools import build_session_server

        folder_path, linked = _working_directory(session)
        server, tool_names = build_session_server(session, user)
        options = _options(session, user, folder_path, linked, server, tool_names)
        asyncio.run(_run(turn, options))
        _finish(message, turn)
    except Exception as exc:  # the service must survive any one turn
        logger.exception("Session turn %s failed", message_id)
        message.status = "failed"
        message.error = f"{type(exc).__name__}: {exc}"[:2000]
        message.content = turn.text
        message.trail = turn.trail
        message.finished_at = timezone.now()
        message.save()
        status_cache.set(
            live_key(message.id),
            {**turn.state("failed"), "error": message.error},
            FINAL_TTL,
        )
    finally:
        status_cache.delete(cancel_key(message.id))
    return message


def _finish(message, turn: Turn):
    session = message.session
    result = turn.result
    if turn.sdk_session_id and session.sdk_session_id != turn.sdk_session_id:
        session.sdk_session_id = turn.sdk_session_id
        session.save(update_fields=["sdk_session_id", "updated_at"])
    if turn.cancelled:
        message.status = "cancelled"
    elif result is None:
        message.status = "failed"
        message.error = "The harness ended without a result."
    elif result.is_error:
        message.status = "failed"
        message.error = (
            "; ".join(result.errors or []) or result.result or result.subtype
        )[:2000]
    else:
        message.status = "done"
    final_text = (result.result if result and result.result else "") or turn.text
    message.content = final_text[:TEXT_CAP]
    message.trail = turn.trail
    message.input_tokens = turn.usage.get("input_tokens")
    message.output_tokens = turn.usage.get("output_tokens")
    message.cache_read_tokens = turn.usage.get("cache_read_input_tokens")
    message.cost_usd = turn.cost
    message.duration_ms = (
        result.duration_ms if result else int((time.monotonic() - turn.started) * 1000)
    )
    message.finished_at = timezone.now()
    message.save()
    status_cache.set(live_key(message.id), turn.state(message.status), FINAL_TTL)
