"""The MCP server a session's agent calls: which tools a user gets, and
the two kinds the sessions add (earlier sessions, saving case law)."""

import asyncio
import json

import pytest

from apps.ai.caselaw_save import save_authority
from apps.ai.models import Session, SessionMessage
from apps.ai.session_tools import build_session_tools, tool_name
from apps.case.models import CaseLaw

from .test_sessions import _login

# The tools run their ORM work on a worker thread, outside the test
# transaction, so the rows must be committed for them to see.
pytestmark = pytest.mark.django_db(transaction=True)


def _handlers(session, user):
    tools = build_session_tools(session, user)
    return [tool_name(t.name) for t in tools], {t.name: t for t in tools}


def _call(tool, **args):
    result = asyncio.run(tool.handler(args))
    return result["content"][0]["text"], bool(result.get("is_error"))


def test_the_tools_follow_the_users_permissions(matter):
    admin = _login("ada", role="ADMIN")
    session = Session.objects.create(matter=matter, user=admin.user)
    names, _ = _handlers(session, admin.user)
    assert tool_name("read_invoice") in names
    assert tool_name("search_caselaw") in names
    assert tool_name("save_caselaw") in names
    assert tool_name("list_sessions") in names

    plain = _login("bob", role="STAFF", perm_financial=False, perm_research=False)
    names, _ = _handlers(session, plain.user)
    assert tool_name("read_invoice") not in names
    assert tool_name("search_caselaw") not in names
    assert tool_name("save_caselaw") not in names
    assert tool_name("read_matter_section") in names


def test_earlier_sessions_can_be_listed_and_read(matter):
    admin = _login("ada", role="ADMIN", first_name="Ada", last_name="A")
    earlier = Session.objects.create(matter=matter, user=admin.user, title="Deadlines")
    SessionMessage.objects.create(
        session=earlier, role="user", content="When is discovery due?", user=admin.user
    )
    SessionMessage.objects.create(
        session=earlier, role="assistant", content="December 1."
    )
    current = Session.objects.create(matter=matter, user=admin.user)
    _, tools = _handlers(current, admin.user)

    text, is_error = _call(tools["list_sessions"])
    assert not is_error
    rows = json.loads(text)
    assert [r["title"] for r in rows] == ["Deadlines"]
    assert rows[0]["messages"] == 2 and rows[0]["started_by"] == "Ada A"

    text, is_error = _call(tools["read_session"], session_id=earlier.id)
    assert not is_error
    assert "# Deadlines" in text and "December 1." in text and "Ada A" in text

    text, is_error = _call(tools["read_session"], session_id=current.id)
    assert is_error  # the current session is not an earlier one


def test_save_caselaw_builds_the_row_from_the_cluster(matter, monkeypatch):
    admin = _login("ada", role="ADMIN")
    session = Session.objects.create(matter=matter, user=admin.user)
    monkeypatch.setattr(
        "apps.case.courtlistener.fetch_cluster",
        lambda cluster_id: {
            "case_name": "Roe v. Wade",
            "citations": [{"volume": 410, "reporter": "U.S.", "page": "113"}],
            "court": "https://www.courtlistener.com/api/rest/v4/courts/scotus/",
            "date_filed": "1973-01-22",
            "docket_number": "70-18",
            "sub_opinions": [
                "https://www.courtlistener.com/api/rest/v4/opinions/108713/"
            ],
            "absolute_url": "/opinion/108713/roe-v-wade/",
        },
    )
    monkeypatch.setattr("apps.case.services.generate_caselaw_summary", lambda pk: None)
    _, tools = _handlers(session, admin.user)

    text, is_error = _call(
        tools["save_caselaw"],
        cluster_id=108713,
        proposition="Privacy covers the decision.",
        court="Supreme Court",
    )
    assert not is_error and "Saved to case law: Roe v. Wade" in text
    row = CaseLaw.objects.get(matter=matter, cluster_id=108713)
    assert row.court == "Supreme Court" and row.court_id == "scotus"
    assert row.opinion_id == 108713 and row.notes == "Privacy covers the decision."
    assert row.created_by == admin.user

    # Saving it again appends the proposition instead of duplicating the row.
    again = save_authority(matter, 108713, "A second point.", "", admin.user)
    assert again.pk == row.pk and CaseLaw.objects.count() == 1
    assert again.notes == "Privacy covers the decision.\nA second point."

    text, is_error = _call(tools["save_caselaw"], cluster_id=0, proposition="x")
    assert is_error


def test_search_files_searches_the_linked_folder(matter, tmp_path, settings):
    settings.FILES_TEXT_CACHE = tmp_path / "cache"
    folder = tmp_path / "Emling"
    (folder / "Corr").mkdir(parents=True)
    (folder / "Corr" / "letter.txt").write_text("Dear counsel, the lender objects.")
    client = _login("ada", role="ADMIN")
    session = Session.objects.create(matter=matter, user=client.user)

    tools = {t.name: t for t in build_session_tools(session, client.user, folder)}
    assert "search_files" in tools
    text, is_error = _call(tools["search_files"], pattern="lender", path="Corr")
    assert not is_error and "Corr/letter.txt" in text and "the lender objects" in text
    text, is_error = _call(tools["search_files"], pattern="")
    assert is_error

    unlinked = {t.name: t for t in build_session_tools(session, client.user, None)}
    text, is_error = _call(unlinked["search_files"], pattern="lender")
    assert is_error and "No folder" in text
