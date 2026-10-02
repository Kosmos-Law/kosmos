"""An edit round's life: collected, claimed, applied, and when it expires.

The chat used to give up on every round after 30 seconds, whether or not
the extension already had it, and then ignored the extension's report. A
user was told "not applied" about edits that were in their document. Now a
round nobody collected expires at 30 seconds and is never handed out; a
collected round is waited on for longer; a 0.4.0 extension claims the round
before applying, so one the chat has given up on is left alone; and a late
report is recorded.

Two extension versions are in use (a user's copy changes only when they
download it again), so the 0.3.0 call sequence is exercised here as well.
"""

import base64
import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.drafts import chat, companion
from apps.drafts.models import CompanionRound, CompanionToken

pytestmark = pytest.mark.django_db

BLOCK = '```draft-edits\n[{"old": "Some text.", "new": "Better text."}]\n```'
EDITS = [{"op": "replace", "old": "a", "new": "b"}]
RESULTS = [{"op": "replace", "replacements": 1}]


@pytest.fixture
def api(user):
    api = Client()
    api.defaults["HTTP_X_KOSMOS_TOKEN"] = CompanionToken.for_user(user).key
    return api


@pytest.fixture(autouse=True)
def _no_pandoc(monkeypatch):
    monkeypatch.setattr(companion.convert, "to_markdown", lambda b, ext: "PUSHED")


def _post(api, path, payload):
    return api.post(path, json.dumps(payload), content_type="application/json")


def _base(link):
    return f"/case/drafts/companion/api/{link.id}"


def _ops(api, link):
    return json.loads(api.get(f"{_base(link)}/ops/").content)["round"]


def _on_each_wait(monkeypatch, step):
    """Run ``step(round)`` in place of each tick of the worker's wait loop.

    A real companion answers from another process; in a test that would
    need a second DB connection, which cannot see the test's transaction.
    """

    def fake_sleep(seconds):
        step(CompanionRound.objects.get())

    monkeypatch.setattr(chat.time, "sleep", fake_sleep)


def _connected(link):
    link.companion_seen = timezone.now()
    link.save()
    return link


# ── The chat worker's two clocks ─────────────────────────────────────────────


def test_uncollected_round_expires_and_says_not_applied(link, monkeypatch):
    monkeypatch.setattr(chat, "COMPANION_WAIT_SECONDS", 0)
    _on_each_wait(monkeypatch, lambda round_: None)

    text = chat.apply_edit_blocks(f"Done.\n\n{BLOCK}", _connected(link))
    assert "were not applied" in text
    assert "did not respond in time" in text
    round_ = CompanionRound.objects.get()
    assert round_.status == "expired"
    assert round_.delivered_at is None


def test_collected_round_outlives_the_pickup_deadline(link, monkeypatch):
    """Collected, and still being applied when the 30 seconds for pickup
    have passed: the worker keeps waiting, and the outcome is believed."""
    monkeypatch.setattr(chat, "COMPANION_WAIT_SECONDS", 0)
    ticks = []

    def step(round_):
        ticks.append(round_.status)
        if len(ticks) == 1:
            round_.delivered_at = timezone.now()
        elif len(ticks) == 4:
            round_.status = "applied"
            round_.result = RESULTS
        round_.save()

    _on_each_wait(monkeypatch, step)
    text = chat.apply_edit_blocks(f"Done.\n\n{BLOCK}", _connected(link))
    assert "Applied 1 edit as tracked changes" in text
    assert len(ticks) == 4
    assert CompanionRound.objects.get().status == "applied"


def test_collected_round_with_no_report_cannot_be_confirmed(link, monkeypatch):
    """The extension has the edits and went quiet. Whether they landed is
    not known, so the chat does not claim either way."""
    monkeypatch.setattr(chat, "COMPANION_WAIT_SECONDS", 0)

    def step(round_):
        round_.delivered_at = timezone.now() - timedelta(
            seconds=chat.COMPANION_APPLY_SECONDS + 1
        )
        round_.save()

    _on_each_wait(monkeypatch, step)
    text = chat.apply_edit_blocks(f"Done.\n\n{BLOCK}", _connected(link))
    assert "could not be confirmed" in text
    assert "if the tracked changes are there, they were applied" in text
    assert "were not applied" not in text
    assert CompanionRound.objects.get().status == "expired"


def test_the_wait_has_a_ceiling(link, monkeypatch):
    """A client that kept re-stamping a round could not hold the chat's
    worker thread for ever."""
    monkeypatch.setattr(chat, "COMPANION_WAIT_SECONDS", 0)
    monkeypatch.setattr(chat, "COMPANION_APPLY_SECONDS", 0)

    def step(round_):
        round_.delivered_at = timezone.now() + timedelta(hours=1)
        round_.save()

    _on_each_wait(monkeypatch, step)
    text = chat.apply_edit_blocks(f"Done.\n\n{BLOCK}", _connected(link))
    assert "could not be confirmed" in text
    assert CompanionRound.objects.get().status == "expired"


# ── The server side of the protocol ──────────────────────────────────────────


def test_an_expired_round_is_never_handed_out(api, link):
    CompanionRound.objects.create(link=link, edits=EDITS, status="expired")
    assert _ops(api, link) is None


def test_ops_asks_the_extension_to_claim(api, link):
    round_ = CompanionRound.objects.create(link=link, edits=EDITS)
    handed = _ops(api, link)
    assert handed == {"id": round_.id, "edits": EDITS, "claim": True}
    round_.refresh_from_db()
    assert round_.delivered_at is not None


def test_claim_is_granted_while_the_chat_is_waiting(api, link):
    round_ = CompanionRound.objects.create(link=link, edits=EDITS)
    _ops(api, link)
    long_ago = timezone.now() - timedelta(seconds=60)
    CompanionRound.objects.filter(pk=round_.pk).update(delivered_at=long_ago)

    answer = _post(api, f"{_base(link)}/rounds/{round_.id}/", {"claim": True})
    assert json.loads(answer.content) == {"status": "drafting", "apply": True}
    round_.refresh_from_db()
    assert round_.status == "pending"
    # The apply clock restarts from the claim.
    assert round_.delivered_at > long_ago + timedelta(seconds=30)


@pytest.mark.parametrize("status", ["expired", "applied", "failed"])
def test_claim_is_refused_once_the_round_is_settled(api, link, status):
    round_ = CompanionRound.objects.create(
        link=link, edits=EDITS, status=status, delivered_at=timezone.now()
    )
    answer = _post(api, f"{_base(link)}/rounds/{round_.id}/", {"claim": True})
    assert json.loads(answer.content)["apply"] is False
    round_.refresh_from_db()
    assert round_.status == status


def test_claim_is_refused_for_a_round_never_collected(api, link):
    round_ = CompanionRound.objects.create(link=link, edits=EDITS)
    answer = _post(api, f"{_base(link)}/rounds/{round_.id}/", {"claim": True})
    assert json.loads(answer.content)["apply"] is False


def test_a_late_applied_report_is_recorded(api, link):
    """The worker gave up on a collected round; the extension then reports
    that it applied the edits. They are in the document: record it, and
    take the document it sends."""
    round_ = CompanionRound.objects.create(
        link=link, edits=EDITS, status="expired", delivered_at=timezone.now()
    )
    payload = {
        "ok": True,
        "results": RESULTS,
        "odt_b64": base64.b64encode(b"x").decode(),
    }
    response = _post(api, f"{_base(link)}/rounds/{round_.id}/", payload)
    assert response.status_code == 200
    round_.refresh_from_db()
    link.refresh_from_db()
    assert round_.status == "applied"
    assert round_.result == RESULTS
    assert link.doc_text == "PUSHED"


def test_a_late_failure_is_recorded_too(api, link):
    round_ = CompanionRound.objects.create(
        link=link, edits=EDITS, status="expired", delivered_at=timezone.now()
    )
    _post(
        api,
        f"{_base(link)}/rounds/{round_.id}/",
        {"ok": False, "error": "text not found", "edit_index": 0},
    )
    round_.refresh_from_db()
    assert round_.status == "failed"
    assert round_.error == "text not found"


def test_a_report_for_a_round_never_handed_out_is_ignored(api, link):
    round_ = CompanionRound.objects.create(link=link, edits=EDITS, status="expired")
    _post(api, f"{_base(link)}/rounds/{round_.id}/", {"ok": True, "results": RESULTS})
    round_.refresh_from_db()
    assert round_.status == "expired"


def test_a_settled_round_is_not_rewritten(api, link):
    round_ = CompanionRound.objects.create(
        link=link,
        edits=EDITS,
        status="failed",
        error="text not found",
        delivered_at=timezone.now(),
    )
    _post(api, f"{_base(link)}/rounds/{round_.id}/", {"ok": True, "results": RESULTS})
    round_.refresh_from_db()
    assert round_.status == "failed"


# ── The 0.3.0 extension against this server ──────────────────────────────────


class TestOldExtension:
    """What the 0.3.0 extension does, call for call (its source is commit
    8d9280f8f's kosmos_companion.py): GET sessions/, POST hello/ with
    odt_b64, GET ops/ every few seconds reading "status" and "round" with
    its "id" and "edits", apply at once, POST rounds/<id>/ with ok, results
    or error and edit_index, and odt_b64. It never claims."""

    def test_sessions_still_carry_what_it_reads(self, api, link):
        session = json.loads(api.get("/case/drafts/companion/api/sessions/").content)[
            "sessions"
        ][0]
        assert session["id"] == link.id
        assert session["name"] == "motion.odt"
        assert session["matter"] == "Smith v Jones"

    def test_connect_poll_apply_report(self, api, link):
        doc = base64.b64encode(b"odt").decode()
        hello = _post(api, f"{_base(link)}/hello/", {"odt_b64": doc})
        assert json.loads(hello.content)["status"] == "drafting"

        idle = json.loads(api.get(f"{_base(link)}/ops/").content)
        assert idle["status"] == "drafting"
        assert idle["round"] is None

        round_ = CompanionRound.objects.create(link=link, edits=EDITS)
        data = json.loads(api.get(f"{_base(link)}/ops/").content)
        assert data["status"] == "drafting"
        assert data["round"]["id"] == round_.id
        assert data["round"]["edits"] == EDITS

        # No claim: it applies, then reports.
        report = _post(
            api,
            f"{_base(link)}/rounds/{round_.id}/",
            {"ok": True, "results": RESULTS, "odt_b64": doc},
        )
        assert json.loads(report.content)["status"] == "drafting"
        round_.refresh_from_db()
        assert round_.status == "applied"
        assert round_.result == RESULTS

    def test_its_failure_report_is_still_understood(self, api, link):
        round_ = CompanionRound.objects.create(link=link, edits=EDITS)
        _ops(api, link)
        _post(
            api,
            f"{_base(link)}/rounds/{round_.id}/",
            {"ok": False, "error": "text not found", "edit_index": 2},
        )
        round_.refresh_from_db()
        assert round_.status == "failed"
        assert round_.edit_index == 2

    def test_unclaimed_round_reaches_the_chat_as_applied(self, api, link, monkeypatch):
        """End to end with the chat worker: the old extension collects the
        round and reports without ever claiming, and the chat says applied."""
        monkeypatch.setattr(chat, "COMPANION_WAIT_SECONDS", 0)
        ticks = []

        def step(round_):
            ticks.append(1)
            if len(ticks) == 1:
                assert _ops(api, link)["id"] == round_.id
            elif len(ticks) == 3:
                _post(
                    api,
                    f"{_base(link)}/rounds/{round_.id}/",
                    {"ok": True, "results": RESULTS},
                )

        _on_each_wait(monkeypatch, step)
        text = chat.apply_edit_blocks(f"Done.\n\n{BLOCK}", _connected(link))
        assert "Applied 1 edit as tracked changes" in text
