"""The session runtime against a scripted harness: what one turn records,
how a cancel lands, how the service's heartbeat gates the page."""

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
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
        lambda session, user: (
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
    assert [s["summary"] for s in answer.trail] == [
        "Glob Evidence/*.pdf",
        "Search: deadline; scheduling order",
    ]
    assert answer.trail[1]["error"] is True and answer.trail[0]["pending"] is False
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
    assert "session-live" in html and 'hx-trigger="every 2s"' in html
    assert "sessions service is not running" in html  # no heartbeat yet
    assert client.post(send, {"message": "again"}).status_code == 409

    runtime.service_heartbeat()
    html = client.get(reverse("ai:session-live", args=[session.id])).content.decode()
    assert "Starting..." in html

    answer = session.messages.get(role="assistant")
    runtime.run_turn(answer.id)
    html = client.get(reverse("ai:session-live", args=[session.id])).content.decode()
    assert "session-live" not in html
    assert "2026-12-01" in html and "2 steps" in html
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
