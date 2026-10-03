"""The LibreOffice extension's own code, as far as it runs without LibreOffice.

kosmos_companion.py imports UNO, which exists only inside LibreOffice. With
those imports stubbed the module loads, and what does not touch a document
or a window can be run: pairing a document with its link, the claim before
applying, the wording of its messages. The poll loop's round handling is
driven against the real server views through the Django test client.

Not covered here, because it needs a running Writer: the chooser dialog
itself, applying edits to a document, and the menu.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest import mock

import pytest
from django.test import Client
from django.utils import timezone

from apps.drafts import companion
from apps.drafts.models import CompanionRound, CompanionToken

SOURCE = Path(companion.COMPANION_SRC) / "kosmos_companion.py"
EDITS = [{"op": "replace", "old": "a", "new": "b"}]
RESULTS = [{"op": "replace", "replacements": 1}]


@pytest.fixture(scope="module")
def ext():
    """The extension module, loaded with UNO stubbed out."""

    class ImplementationHelper:
        def addImplementation(self, *args):
            pass

    uno = types.ModuleType("uno")
    unohelper = types.ModuleType("unohelper")
    unohelper.Base = type("Base", (), {})
    unohelper.ImplementationHelper = ImplementationHelper
    lang = types.ModuleType("com.sun.star.lang")
    lang.DisposedException = type("DisposedException", (Exception,), {})
    task = types.ModuleType("com.sun.star.task")
    task.XJobExecutor = type("XJobExecutor", (), {})
    stubs = {
        "uno": uno,
        "unohelper": unohelper,
        "com": types.ModuleType("com"),
        "com.sun": types.ModuleType("com.sun"),
        "com.sun.star": types.ModuleType("com.sun.star"),
        "com.sun.star.lang": lang,
        "com.sun.star.task": task,
    }
    with mock.patch.dict(sys.modules, stubs):
        spec = importlib.util.spec_from_file_location("kosmos_companion_test", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


# ── Pairing ──────────────────────────────────────────────────────────────────


SESSIONS = [
    {
        "id": 3,
        "name": "motion.odt",
        "matter": "Smith v Jones",
        "conversation": "Reply",
        "file": "drive-smith",
    },
    {
        "id": 2,
        "name": "brief.odt",
        "matter": "Smith v Jones",
        "conversation": "Brief",
        "file": "drive-brief",
    },
    {
        "id": 1,
        "name": "motion.odt",
        "matter": "Doe v Roe",
        "conversation": "Motion",
        "file": "drive-doe",
    },
]
# A second conversation linking the same file as SESSIONS[0].
SIBLING = {
    "id": 4,
    "name": "motion.odt",
    "matter": "Smith v Jones",
    "conversation": "Second chat",
    "file": "drive-smith",
}


def test_matching_is_by_file_name_in_the_servers_order(ext):
    matches = ext._matching_sessions(SESSIONS, "motion.odt")
    assert [s["id"] for s in matches] == [3, 1]
    assert ext._matching_sessions(SESSIONS, "brief.odt")[0]["id"] == 2
    assert ext._matching_sessions(SESSIONS, "other.odt") == []


def test_links_to_one_file_are_one_document(ext):
    """Several conversations linking the same file share a connection on
    the server: there is nothing to choose between."""
    documents = ext._distinct_documents([SIBLING, SESSIONS[0]])
    assert [s["id"] for s in documents] == [4]


def test_links_to_different_files_are_different_documents(ext):
    documents = ext._distinct_documents([SIBLING, SESSIONS[0], SESSIONS[2]])
    assert [s["id"] for s in documents] == [4, 1]


def test_an_older_server_names_no_file_so_matters_tell_them_apart(ext):
    old = [
        {"id": 3, "name": "motion.odt", "matter": "Smith v Jones"},
        {"id": 2, "name": "motion.odt", "matter": "Smith v Jones"},
        {"id": 1, "name": "motion.odt", "matter": "Doe v Roe"},
    ]
    assert [s["id"] for s in ext._distinct_documents(old)] == [3, 1]


def test_label_names_matter_and_conversation(ext):
    assert ext._session_label(SESSIONS[0]) == "Smith v Jones: Reply"
    assert ext._session_label(SESSIONS[2]) == "Doe v Roe: Motion"


def test_label_copes_with_a_server_that_sends_no_conversation(ext):
    assert ext._session_label({"id": 1, "name": "m.odt", "matter": "Doe"}) == "Doe"
    assert ext._session_label({"id": 1, "name": "m.odt", "matter": ""}) == "No matter"


class _Window:
    """Stands in for Writer: records messages, answers the chooser."""

    def __init__(self, ext, sessions, choice):
        self.messages = []
        self.asked = []
        self.hello = []
        companion_ = ext.Companion(ctx=None)
        companion_._message = lambda text, title="": self.messages.append(text)

        def choose(doc_name, matches):
            self.asked.append([s["id"] for s in matches])
            if isinstance(choice, Exception):
                raise choice
            return choice

        companion_._choose_session = choose
        doc = mock.Mock()
        doc.supportsService.return_value = True
        doc.getURL.return_value = "file:///drive/motion.odt"
        desktop = mock.Mock()
        desktop.getCurrentComponent.return_value = doc
        companion_._desktop = lambda: desktop
        api = mock.Mock()
        api.sessions.return_value = sessions
        api.hello.side_effect = lambda session_id, odt: self.hello.append(session_id)
        self.api = api
        self.companion = companion_


@pytest.fixture
def writer(ext, monkeypatch):
    """Run the Connect command with Writer, the config file and the network
    faked. Returns a function: (sessions, choice) -> _Window."""
    monkeypatch.setattr(ext, "_load_config", lambda: ("https://kosmos.example", "t"))
    monkeypatch.setattr(ext, "_export_odt_b64", lambda doc: "b64")
    monkeypatch.setattr(
        ext.uno, "fileUrlToSystemPath", lambda url: "/drive/motion.odt", raising=False
    )
    monkeypatch.setattr(ext, "_connection", None)
    started = []

    class Connection:
        def __init__(self, ctx, api, doc, session):
            self.session = session
            self.thread = mock.Mock()
            self.stop = mock.Mock()
            started.append(session["id"])

    monkeypatch.setattr(ext, "_Connection", Connection)

    def connect(sessions, choice=None):
        window = _Window(ext, sessions, choice)
        monkeypatch.setattr(ext, "Api", lambda server, token: window.api)
        window.companion._connect()
        window.started = list(started)
        started.clear()
        return window

    return connect


def test_one_match_connects_without_asking(writer):
    window = writer([SESSIONS[0], SESSIONS[1]])
    assert window.asked == []
    assert window.hello == [3]
    assert window.started == [3]
    assert "Smith v Jones: Reply" in window.messages[-1]


def test_sibling_links_to_one_file_connect_without_asking(writer):
    """Two conversations on the same file, a supported everyday case: the
    newest is taken, as 0.3.0 did, and nobody is asked."""
    window = writer([SIBLING, SESSIONS[0]])
    assert window.asked == []
    assert window.hello == [4]


def test_several_matches_ask_and_connect_to_the_choice(writer):
    window = writer(SESSIONS, choice=1)
    assert window.asked == [[3, 1]]
    assert window.hello == [1]
    assert window.started == [1]
    # The confirmation names the matter the document is now paired with.
    assert "Doe v Roe: Motion" in window.messages[-1]


def test_cancelling_the_chooser_connects_to_nothing(writer):
    window = writer(SESSIONS, choice=None)
    assert window.asked == [[3, 1]]
    assert window.hello == []
    assert window.started == []
    assert window.messages == []


def test_a_chooser_that_cannot_be_shown_falls_back_to_the_newest_link(writer):
    window = writer(SESSIONS, choice=RuntimeError("no toolkit"))
    assert window.hello == [3]
    assert "Smith v Jones: Reply" in window.messages[-1]


def test_no_match_explains_where_to_link(writer):
    window = writer([SESSIONS[1]])
    assert window.hello == []
    message = window.messages[-1]
    assert 'No draft link found for "motion.odt"' in message
    assert "pen button beside the message box" in message
    assert "Link a Draft" in message


# ── Wording ──────────────────────────────────────────────────────────────────


def test_messages_use_the_applications_names():
    source = SOURCE.read_text(encoding="utf-8")
    for stale in (
        "paperclip",
        "chat header",
        "settled in Kosmos",
        "link-a-draft dialog",
        "start a drafting session",
        "server's copy of the draft",
    ):
        assert stale not in source, stale
    assert "—" not in source


# ── Claim before apply, against the real server views ────────────────────────


class ClientApi:
    """The extension's Api, with the Django test client for a network."""

    def __init__(self, client, base):
        self.client = client
        self.base = base
        self.calls = []

    def _call(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET":
            response = self.client.get(self.base + path)
        else:
            response = self.client.post(
                self.base + path, json.dumps(payload), content_type="application/json"
            )
        assert response.status_code == 200, response.status_code
        return json.loads(response.content)


@pytest.fixture
def connection(ext, link, user, monkeypatch):
    """A connected extension: its real Api methods and round handling, the
    real server, and a document that records what was applied to it."""
    client = Client()
    client.defaults["HTTP_X_KOSMOS_TOKEN"] = CompanionToken.for_user(user).key
    api = ext.Api("https://unused", "unused")
    transport = ClientApi(client, "/case/drafts/companion/api")
    api._call = transport._call
    applied = []

    def fake_apply(ctx, doc, edits):
        applied.append(edits)
        return RESULTS

    monkeypatch.setattr(ext, "_apply_round", fake_apply)
    monkeypatch.setattr(ext, "_export_odt_b64", lambda doc: "eA==")
    monkeypatch.setattr(companion.convert, "to_markdown", lambda b, e: "PUSHED")
    conn = ext._Connection(
        ctx=None,
        api=api,
        doc=object(),
        session={"id": link.id, "name": link.name, "matter": "Smith v Jones"},
    )
    conn.applied = applied
    conn.calls = transport.calls
    return conn


@pytest.mark.django_db
def test_round_is_claimed_then_applied_then_reported(connection, link):
    round_ = CompanionRound.objects.create(link=link, edits=EDITS)
    handed = connection.api.ops(link.id)["round"]
    connection._handle_round(handed)

    assert connection.applied == [EDITS]
    path = f"/{link.id}/rounds/{round_.id}/"
    assert [(m, p) for m, p, _ in connection.calls] == [
        ("GET", f"/{link.id}/ops/"),
        ("POST", path),
        ("POST", path),
    ]
    assert connection.calls[1][2] == {"claim": True}
    round_.refresh_from_db()
    assert round_.status == "applied"
    assert round_.result == RESULTS


@pytest.mark.django_db
def test_round_the_chat_gave_up_on_is_left_alone(connection, link):
    """Collected, then the chat's wait ran out before the extension got to
    it. The user has been told the edits were not applied: they must not
    appear in the document afterwards."""
    round_ = CompanionRound.objects.create(link=link, edits=EDITS)
    handed = connection.api.ops(link.id)["round"]
    CompanionRound.objects.filter(pk=round_.pk).update(status="expired")

    connection._handle_round(handed)
    assert connection.applied == []
    assert len(connection.calls) == 2  # ops, then the refused claim; no report
    assert "stopped waiting" in connection.last_note
    round_.refresh_from_db()
    assert round_.status == "expired"


@pytest.mark.django_db
def test_round_from_a_server_without_claims_is_applied_directly(connection, link):
    """A server that predates the claim hands out a round with no "claim"
    key. The extension must not send it one: that server would read the
    claim as a failed result."""
    round_ = CompanionRound.objects.create(
        link=link, edits=EDITS, delivered_at=timezone.now()
    )
    connection._handle_round({"id": round_.id, "edits": EDITS})

    assert connection.applied == [EDITS]
    assert len(connection.calls) == 1
    assert "claim" not in connection.calls[0][2]
    round_.refresh_from_db()
    assert round_.status == "applied"


@pytest.mark.django_db
def test_a_claim_that_cannot_be_made_applies_nothing(connection, link, monkeypatch):
    round_ = CompanionRound.objects.create(link=link, edits=EDITS)
    handed = connection.api.ops(link.id)["round"]

    def offline(session_id, round_id):
        raise OSError("network is unreachable")

    monkeypatch.setattr(connection.api, "claim", offline)
    with pytest.raises(OSError):
        connection._handle_round(handed)
    assert connection.applied == []
    round_.refresh_from_db()
    assert round_.status == "pending"
