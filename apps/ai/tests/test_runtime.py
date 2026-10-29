"""The session runtime against a scripted harness: what one turn records,
how a cancel lands, how the service's heartbeat gates the page."""

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from django.urls import reverse

from apps.ai import runtime
from apps.ai.models import Session, SessionMessage
from apps.matters.models import Matter
from apps.settings.models import Firm

from .test_sessions import _login

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def firm():
    return Firm.objects.create(name="Test Firm LLC")


@pytest.fixture
def matter():
    return Matter.objects.create(name="Smith v Jones", status="Open")


def scripted_messages():
    return [
        SystemMessage(subtype="init", data={"session_id": "sdk-abc"}),
        AssistantMessage(
            content=[
                ThinkingBlock(
                    thinking="The deadlines will be in the scheduling order.",
                    signature="s",
                ),
                TextBlock(text="Let me look at the evidence folder."),
                ToolUseBlock(id="t1", name="Glob", input={"pattern": "Evidence/*.pdf"}),
            ],
            model="claude-opus-5-5",
            usage={"input_tokens": 1200, "output_tokens": 40},
        ),
        UserMessage(
            content=[ToolResultBlock(tool_use_id="t1", content="a.pdf", is_error=False)]
        ),
        AssistantMessage(
            content=[
                ToolUseBlock(
                    id="t2",
                    name="mcp__kosmos__search_materials",
                    input={"queries": ["deadline", "scheduling order"]},
                )
            ],
            model="claude-opus-5-5",
        ),
        UserMessage(
            content=[ToolResultBlock(tool_use_id="t2", content="{}", is_error=True)]
        ),
        AssistantMessage(
            content=[TextBlock(text="The discovery deadline is **2026-12-01**.")],
            model="claude-opus-5-5",
        ),
        ResultMessage(
            subtype="success",
            duration_ms=4321,
            duration_api_ms=4000,
            is_error=False,
            num_turns=3,
            session_id="sdk-abc",
            total_cost_usd=0.1234,
            usage={
                "input_tokens": 5000,
                "output_tokens": 300,
                "cache_read_input_tokens": 2000,
            },
            result="The discovery deadline is **2026-12-01**.",
        ),
    ]


class FakeClient:
    """Stands in for ClaudeSDKClient: yields the script, records calls."""

    script = scripted_messages()
    queries = []
    interrupted = False
    options = None

    def __init__(self, options=None):
        FakeClient.options = options

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, prompt):
        FakeClient.queries.append(prompt)

    async def interrupt(self):
        FakeClient.interrupted = True

    async def receive_response(self):
        for msg in FakeClient.script:
            yield msg
            if FakeClient.interrupted:
                return


class FakeCache(dict):
    """The runtime's status cache, in memory: the real one is a database
    table and the turn's thread hops would need a second connection."""

    def set(self, key, value, timeout=None):
        self[key] = value

    def delete(self, key):
        self.pop(key, None)


@pytest.fixture
def harness(monkeypatch, settings, tmp_path):
    import claude_agent_sdk

    FakeClient.script = scripted_messages()
    FakeClient.queries = []
    FakeClient.interrupted = False
    FakeClient.cache = FakeCache()
    monkeypatch.setattr(claude_agent_sdk, "ClaudeSDKClient", FakeClient)
    monkeypatch.setattr(runtime, "status_cache", FakeClient.cache)
    monkeypatch.setattr(
        "apps.ai.session_tools.build_session_server",
        lambda session, user, folder=None: (
            {"type": "sdk", "name": "kosmos", "instance": None},
            ["mcp__kosmos__x"],
        ),
    )
    settings.SESSIONS_HOME = tmp_path / "home"
    settings.SESSIONS_SCRATCH = tmp_path / "scratch"
    settings.DROPBOX_FIRM_ROOT = None
    return FakeClient


def _turn(matter, user, prompt="What are the deadlines?"):
    session = Session.objects.create(matter=matter, user=user)
    SessionMessage.objects.create(
        session=session, role="user", content=prompt, user=user
    )
    answer = SessionMessage.objects.create(
        session=session, role="assistant", content="", user=user, status="pending"
    )
    return session, answer


def test_a_turn_records_the_answer_trail_usage_and_harness_session(harness, matter):
    client = _login("ada", role="ADMIN", first_name="Ada", last_name="A")
    session, answer = _turn(matter, client.user)

    runtime.run_turn(answer.id)

    answer.refresh_from_db()
    session.refresh_from_db()
    assert answer.status == "done"
    assert answer.content == "The discovery deadline is **2026-12-01**."
    # The trail is the turn in order: narration, then each call with its
    # outcome; the final text is the answer, not a step.
    assert [e["kind"] for e in answer.trail] == ["thinking", "text", "tool", "tool"]
    assert answer.trail[1]["text"] == "Let me look at the evidence folder."
    assert [e["summary"] for e in answer.trail[2:]] == [
        "Glob Evidence/*.pdf",
        "Search: deadline; scheduling order",
    ]
    glob, search = answer.trail[2:]
    assert glob["pending"] is False and glob["outcome"] == "a.pdf"
    assert glob["input"] == "pattern: Evidence/*.pdf"
    assert search["error"] is True and search["outcome"] == "{}"
    assert (answer.input_tokens, answer.output_tokens, answer.cache_read_tokens) == (
        5000,
        300,
        2000,
    )
    assert float(answer.cost_usd) == pytest.approx(0.1234)
    assert answer.duration_ms == 4321
    assert session.sdk_session_id == "sdk-abc"
    assert harness.queries == ["What are the deadlines?"]

    options = harness.options
    assert options.model == "claude-opus-5-5"
    assert options.resume is None
    assert options.permission_mode == "dontAsk"
    assert options.tools == ["Read", "Grep", "Glob"]
    assert "mcp__kosmos__x" in options.allowed_tools
    assert options.setting_sources == []
    assert options.env["CLAUDE_CONFIG_DIR"].endswith("home")
    assert options.cwd.endswith(f"scratch/{session.id}")  # no folder linked
    assert "Smith v Jones" in options.system_prompt
    assert "No folder is linked" in options.system_prompt

    live = harness.cache.get(runtime.live_key(answer.id))
    assert live["status"] == "done" and live["steps"] == 2


def test_the_next_turn_resumes_the_harness_session(harness, matter):
    client = _login("ada", role="ADMIN")
    session, answer = _turn(matter, client.user)
    session.sdk_session_id = "sdk-earlier"
    session.save()
    runtime.run_turn(answer.id)
    assert harness.options.resume == "sdk-earlier"


def test_a_harness_error_marks_the_turn_failed(harness, matter):
    client = _login("ada", role="ADMIN")
    session, answer = _turn(matter, client.user)
    harness.script = harness.script[:1] + [
        ResultMessage(
            subtype="error_max_turns",
            duration_ms=10,
            duration_api_ms=10,
            is_error=True,
            num_turns=80,
            session_id="sdk-abc",
            errors=["Reached max turns"],
        )
    ]
    runtime.run_turn(answer.id)
    answer.refresh_from_db()
    assert answer.status == "failed"
    assert "max turns" in answer.error


def test_an_exception_in_the_harness_is_recorded_not_raised(
    harness, matter, monkeypatch
):
    client = _login("ada", role="ADMIN")
    session, answer = _turn(matter, client.user)

    async def boom(turn, options):
        raise RuntimeError("claude binary missing")

    monkeypatch.setattr(runtime, "_run", boom)
    runtime.run_turn(answer.id)
    answer.refresh_from_db()
    assert answer.status == "failed"
    assert "claude binary missing" in answer.error


def test_a_cancel_flag_interrupts_the_turn(harness, matter):
    client = _login("ada", role="ADMIN")
    session, answer = _turn(matter, client.user)
    harness.cache.set(runtime.cancel_key(answer.id), True, 60)
    runtime.run_turn(answer.id)
    answer.refresh_from_db()
    assert harness.interrupted
    assert answer.status == "cancelled"


def test_send_opens_a_turn_and_the_page_polls_until_it_closes(harness, matter):
    client = _login("ada", role="ADMIN", first_name="Ada", last_name="A")
    session = Session.objects.create(matter=matter, user=client.user)
    send = reverse("ai:session-send", args=[session.id])
    html = client.post(send, {"message": "Deadlines?"}).content.decode()
    assert "session-live" in html and 'hx-trigger="every 1s"' in html
    assert "sessions service is not running" in html  # no heartbeat yet
    assert client.post(send, {"message": "again"}).status_code == 409

    runtime.service_heartbeat()
    html = client.get(reverse("ai:session-live", args=[session.id])).content.decode()
    assert "Starting" in html

    answer = session.messages.get(role="assistant")
    runtime.run_turn(answer.id)
    html = client.get(reverse("ai:session-live", args=[session.id])).content.decode()
    assert "session-live" not in html
    assert "2026-12-01" in html and "Worked for 4s" in html and "2 steps" in html
    # The thought is a collapsed row with a peek at its first line.
    assert (
        "Thought" in html and "The deadlines will be in the scheduling order." in html
    )
    assert "Let me look at the evidence folder." in html  # the narration, in the fold
    assert "this session" in html  # totals line


def test_cancel_before_pickup_closes_the_turn_without_the_harness(harness, matter):
    client = _login("ada", role="ADMIN")
    session = Session.objects.create(matter=matter, user=client.user)
    client.post(
        reverse("ai:session-send", args=[session.id]), {"message": "Deadlines?"}
    )
    assert (
        client.post(reverse("ai:session-cancel", args=[session.id])).status_code == 204
    )
    assert session.messages.get(role="assistant").status == "cancelled"


def _event(**event):
    from claude_agent_sdk import StreamEvent

    return StreamEvent(uuid="u", session_id="s", event=event)


def test_the_live_state_streams_text_and_shows_the_current_call(harness, matter):
    """Stream events put the text being written ahead of its block, and
    name the call being prepared; the full block replaces the draft."""
    client = _login("ada", role="ADMIN")
    session, answer = _turn(matter, client.user)
    turn = runtime.Turn(answer, cwd="/x")

    turn.on_message(
        _event(
            type="content_block_start",
            index=0,
            content_block={"type": "text", "text": ""},
        )
    )
    turn.on_message(
        _event(
            type="content_block_delta",
            index=0,
            delta={"type": "text_delta", "text": "Looking at "},
        )
    )
    turn.on_message(
        _event(
            type="content_block_delta",
            index=0,
            delta={"type": "text_delta", "text": "the folder."},
        )
    )
    state = turn.state()
    assert state["events"][-1] == {
        "kind": "text",
        "text": "Looking at the folder.",
        "draft": True,
    }
    assert state["activity"] == "Writing"

    turn.on_message(
        _event(
            type="content_block_start",
            index=1,
            content_block={"type": "tool_use", "id": "t9", "name": "Read", "input": {}},
        )
    )
    assert turn.state()["activity"] == "Read ..."

    turn.on_message(
        AssistantMessage(
            content=[
                TextBlock(text="Looking at the folder."),
                ToolUseBlock(
                    id="t9", name="Read", input={"file_path": "/x/Evidence/TRO.pdf"}
                ),
            ],
            model="claude-opus-5-5",
        )
    )
    state = turn.state()
    assert [e["kind"] for e in state["events"]] == ["text", "tool"]  # the draft is gone
    assert state["events"][1]["input"] == "file_path: Evidence/TRO.pdf"
    assert state["activity"] == "Read TRO.pdf" and state["steps"] == 1

    turn.on_message(
        UserMessage(
            content=[
                ToolResultBlock(tool_use_id="t9", content="line\n" * 40, is_error=False)
            ]
        )
    )
    assert turn.state()["events"][1]["outcome"] == "40 lines"
    assert turn.state()["activity"] == "Thinking"


def test_the_harness_pdf_notice_becomes_a_size_and_the_folder_path_is_dropped():
    cwd = "/home/x/Dropbox/Firm/Matters/Emling"
    notice = f"PDF file read: {cwd}/Record/Order.pdf (103.3KB)"
    assert runtime._tool_outcome("Read", notice, False, cwd) == "PDF, 103.3KB"
    pages = f"PDF pages extracted: 3 page(s) from {cwd}/Record/Mot.pdf (13.5MB)"
    assert runtime._tool_outcome("Read", pages, False, cwd) == "3 pages, 13.5MB"
    error = f"File does not exist. Note: your current working directory is {cwd}."
    assert runtime._tool_outcome("Read", error, True, cwd) == "File does not exist."
    assert runtime._tool_outcome("Grep", "No files found", False) == "No files found"
    report = "6 hits in 1 of 33 files for 'the lender' under Record:\n\nRecord/x.pdf\n  p.2: ..."
    assert (
        runtime._tool_outcome("search_files", report, False)
        == "6 hits in 1 of 33 files under Record"
    )
    assert (
        runtime._tool_outcome("search_files", "No hits for 'zebra' in 33 files.", False)
        == "No hits in 33 files."
    )
    assert runtime._tool_outcome("Grep", "a\nb\nc\nd", False) == "4 lines"


def test_reasoning_streams_as_a_collapsed_thought(harness, matter):
    from claude_agent_sdk import ThinkingBlock

    client = _login("ada", role="ADMIN")
    session, answer = _turn(matter, client.user)
    turn = runtime.Turn(answer, cwd="/x")
    turn.on_message(
        _event(
            type="content_block_start",
            index=0,
            content_block={"type": "thinking", "thinking": ""},
        )
    )
    turn.on_message(
        _event(
            type="content_block_delta",
            index=0,
            delta={
                "type": "thinking_delta",
                "thinking": "The user wants the deadlines.\nI should read the order.",
            },
        )
    )
    state = turn.state()
    assert (
        state["events"][-1]["kind"] == "thinking"
        and state["events"][-1]["draft"] is True
    )
    assert state["activity"] == "Thinking"
    turn.on_message(
        AssistantMessage(
            content=[
                ThinkingBlock(
                    thinking="The user wants the deadlines.\nI should read the order.",
                    signature="s",
                )
            ],
            model="claude-opus-5-5",
        )
    )
    state = turn.state()
    assert [e["kind"] for e in state["events"]] == ["thinking"]
    assert state["events"][0]["ms"] is not None and "draft" not in state["events"][0]
