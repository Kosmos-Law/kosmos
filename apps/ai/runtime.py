"""One session turn, run by the Claude Agent SDK.

``run_turn(message_id)`` fills one pending assistant message: it starts
the harness (the Claude Code binary) in the matter's folder with the
session's model, the session prompt and the Kosmos tools as an
in-process MCP server, feeds it the prompt, and records what comes back.
The transcript is the harness's (resumed by ``sdk_session_id`` on the
next turn); Kosmos keeps the prompt, the answer, the readable trail and
the cost.

Live progress (the turn's events: narration, reasoning, each tool call
with its outcome, and the text being streamed) goes to the ``ai_status``
cache under the message's key, which the page polls; a cancel flag in
the same cache interrupts the turn. The sessions service (``manage.py run_sessions``) is what calls
this, on a thread per turn.
"""

import asyncio
import json
import logging
import re
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
    if short == "search_files":
        where = tool_input.get("path") or ""
        return f"Search files for '{tool_input.get('pattern', '')}'" + (
            f" in {where}" if where else ""
        )
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


def _text_of(content) -> str:
    """The text of a tool result: a string, or text blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(block.get("text", "")) for block in content if isinstance(block, dict)
        )
    return ""


def _tool_input(name: str, tool_input: dict, cwd: str) -> str:
    """What the call asked for, in one short line, for the step's detail."""
    short = name.split("__")[-1]
    if short in ("Read", "Grep", "Glob"):
        parts = []
        for key in ("file_path", "pattern", "path", "glob"):
            value = tool_input.get(key)
            if value:
                value = str(value)
                if cwd and value.startswith(cwd):
                    value = value[len(cwd) :].lstrip("/") or "."
                parts.append(f"{key}: {value}")
        return "  ".join(parts)[:300]
    try:
        return json.dumps(tool_input, ensure_ascii=False)[:300]
    except (TypeError, ValueError):
        return str(tool_input)[:300]


_PDF_NOTICE = re.compile(
    r"^PDF (?:file read|pages extracted): (?:(\d+) page\(s\) from )?.*\(([\d.]+ ?[KMG]?B)\)$",
    re.S,
)


def _tool_outcome(name: str, text: str, is_error: bool, cwd: str = "") -> str:
    """The elbow line under a finished call: an error, a size, or the
    text itself when it is short."""
    text = text.strip()
    if cwd:
        text = text.replace(cwd + "/", "").replace(cwd, ".")
    if is_error:
        # The harness appends its working directory to a missing-file
        # error; the reader knows the folder.
        text = re.sub(
            r"\s*Note: your current working directory is .*$", "", text, flags=re.S
        )
        return (text.splitlines() or ["error"])[0][:200]
    if not text:
        return "nothing"
    # The harness answers a PDF read with a notice (the pages travel as a
    # document block); its size and page count are the outcome.
    notice = _PDF_NOTICE.match(text)
    if notice:
        pages, size = notice.groups()
        return f"{pages} pages, {size}" if pages else f"PDF, {size}"
    lines = text.count("\n") + 1
    short = name.split("__")[-1]
    # A file search reports itself on its first line: the counts, less
    # the pattern the call line already shows.
    if short == "search_files":
        first = text.splitlines()[0].rstrip(":")
        return re.sub(r" for '.*?'(?= under | in | *$)", "", first)[:160]
    # A one-line answer ("No files found", a number, a short value) is
    # its own outcome; longer results are counted.
    if lines == 1 and len(text) <= 160:
        return text
    if short == "Glob":
        return f"{lines} files"
    return f"{lines} lines"


class Turn:
    """The state of one running turn, flushed to the cache as it goes.

    ``events`` is the turn's transcript so far, in order: the model's
    narration (``text``), its reasoning when the harness shows it
    (``thinking``) and each tool call (``tool``) with what it asked for
    and what came back. The page renders the same list live and, once
    the turn is saved, from the message's trail. ``draft`` is the text
    of the block being streamed, shown ahead of its full block.
    """

    def __init__(self, message, cwd=""):
        self.message = message
        self.session = message.session
        self.cwd = cwd
        self.events = []
        self.draft = ""
        self.draft_thinking = ""
        self.draft_tool = None
        self._thinking_started = None
        self.started = time.monotonic()
        self.usage = {}
        self.cost = None
        self.sdk_session_id = ""
        self.cancelled = False
        self.prompt = ""
        self.result = None
        self._tool_started = {}
        self._last_flush = 0.0

    @property
    def text(self) -> str:
        """The narration so far, for a turn that ends without a result."""
        return "\n\n".join(e["text"] for e in self.events if e["kind"] == "text")

    def activity(self) -> str:
        for event in reversed(self.events):
            if event["kind"] == "tool" and event.get("pending"):
                return event["summary"]
            break
        if self.draft_tool:
            return _step_summary(self.draft_tool["name"], {}) + "..."
        if self.draft and not self.draft_thinking:
            return "Writing"
        return "Thinking"

    def state(self, status="running"):
        events = self.events[-80:]
        if self.draft_thinking.strip():
            events = events + [
                {"kind": "thinking", "text": self.draft_thinking[-4000:], "draft": True}
            ]
        if self.draft.strip():
            events = events + [
                {"kind": "text", "text": self.draft[-20_000:], "draft": True}
            ]
        return {
            "status": status,
            "events": events,
            "steps": sum(1 for e in self.events if e["kind"] == "tool"),
            "activity": self.activity(),
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
            StreamEvent,
            SystemMessage,
            TextBlock,
            ThinkingBlock,
            ToolResultBlock,
            ToolUseBlock,
            UserMessage,
        )

        if isinstance(msg, StreamEvent):
            self._on_stream_event(msg.event or {})
        elif isinstance(msg, SystemMessage):
            if msg.subtype == "init":
                self.sdk_session_id = msg.data.get("session_id") or self.sdk_session_id
        elif isinstance(msg, AssistantMessage):
            self.draft = ""
            self.draft_thinking = ""
            self.draft_tool = None
            for block in msg.content:
                if isinstance(block, TextBlock):
                    if block.text.strip():
                        self.events.append({"kind": "text", "text": block.text.strip()})
                elif isinstance(block, ThinkingBlock):
                    if block.thinking.strip():
                        ms = None
                        if self._thinking_started is not None:
                            ms = int((time.monotonic() - self._thinking_started) * 1000)
                            self._thinking_started = None
                        self.events.append(
                            {
                                "kind": "thinking",
                                "text": block.thinking.strip()[:8000],
                                "ms": ms,
                            }
                        )
                elif isinstance(block, ToolUseBlock):
                    tool_input = block.input or {}
                    self._tool_started[block.id] = time.monotonic()
                    self.events.append(
                        {
                            "kind": "tool",
                            "id": block.id,
                            "name": block.name,
                            "summary": _step_summary(block.name, tool_input),
                            "input": _tool_input(block.name, tool_input, self.cwd),
                            "outcome": "",
                            "preview": "",
                            "pending": True,
                            "error": False,
                            "ms": None,
                        }
                    )
            if msg.usage:
                self.usage = _merge_usage(self.usage, msg.usage)
        elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    self._on_tool_result(block)
        elif isinstance(msg, ResultMessage):
            self.sdk_session_id = msg.session_id or self.sdk_session_id
            if msg.usage:
                self.usage = _merge_usage({}, msg.usage)
            self.cost = msg.total_cost_usd
            self.result = msg

    def _on_stream_event(self, event: dict):
        kind = event.get("type")
        if kind == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                self.draft_tool = {"id": block.get("id"), "name": block.get("name", "")}
            elif block.get("type") == "text":
                self.draft = ""
            elif block.get("type") == "thinking":
                self.draft_thinking = ""
                self._thinking_started = time.monotonic()
        elif kind == "content_block_delta":
            delta = event.get("delta") or {}
            if delta.get("type") == "text_delta":
                self.draft += delta.get("text", "")
            elif delta.get("type") == "thinking_delta":
                self.draft_thinking += delta.get("thinking", "")
        elif kind == "content_block_stop":
            self.draft_tool = None

    def _on_tool_result(self, block):
        text = _text_of(block.content)
        for step in self.events:
            if step["kind"] == "tool" and step["id"] == block.tool_use_id:
                started = self._tool_started.get(block.tool_use_id)
                step["pending"] = False
                step["error"] = bool(block.is_error)
                step["outcome"] = _tool_outcome(
                    step["name"], text, bool(block.is_error), self.cwd
                )
                preview = text.strip()
                if self.cwd:
                    preview = preview.replace(self.cwd + "/", "")
                step["preview"] = preview[:600]
                step["ms"] = (
                    int((time.monotonic() - started) * 1000) if started else None
                )


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
        effort=session.effort or "high",
        include_partial_messages=True,
        # The model's reasoning, summarized, so the page can show it; the
        # newer models send only a signature unless asked.
        thinking={"type": "adaptive", "display": "summarized"},
        # A tool result travels as one JSON line on the harness's stdout;
        # a long PDF read overflows the SDK's 1 MB default.
        max_buffer_size=64 * 1024 * 1024,
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

    folder_path, linked = _working_directory(session)
    # The harness keeps its transcripts and config here; a fresh host
    # has no such directory yet.
    Path(settings.SESSIONS_HOME).mkdir(parents=True, exist_ok=True)
    turn = Turn(message, cwd=str(folder_path))
    turn.prompt = prompt_row.content if prompt_row else ""
    turn.flush(force=True)
    try:
        from .session_tools import build_session_server

        server, tool_names = build_session_server(
            session, user, folder_path if linked else None
        )
        options = _options(session, user, folder_path, linked, server, tool_names)
        asyncio.run(_run(turn, options))
        _finish(message, turn)
    except Exception as exc:  # the service must survive any one turn
        logger.exception("Session turn %s failed", message_id)
        message.status = "failed"
        message.error = f"{type(exc).__name__}: {exc}"[:2000]
        message.content = turn.text
        message.trail = turn.events
        message.finished_at = timezone.now()
        message.duration_ms = int((time.monotonic() - turn.started) * 1000)
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
    events = list(turn.events)
    # The answer is the last thing the model said; it is shown as the
    # message, not repeated at the end of the steps.
    if (
        events
        and events[-1]["kind"] == "text"
        and events[-1]["text"] == final_text.strip()
    ):
        events.pop()
    message.content = final_text[:TEXT_CAP]
    message.trail = events
    # The harness reports the uncached input, the cache writes and the
    # cache reads apart; the message keeps what was sent (uncached plus
    # written) as its input, and the cache reads beside it.
    usage = turn.usage
    if usage:
        message.input_tokens = (usage.get("input_tokens") or 0) + (
            usage.get("cache_creation_input_tokens") or 0
        )
        message.output_tokens = usage.get("output_tokens")
        message.cache_read_tokens = usage.get("cache_read_input_tokens")
    message.cost_usd = turn.cost
    message.duration_ms = (
        result.duration_ms if result else int((time.monotonic() - turn.started) * 1000)
    )
    message.finished_at = timezone.now()
    message.save()
    status_cache.set(live_key(message.id), turn.state(message.status), FINAL_TTL)
