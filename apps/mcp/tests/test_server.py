"""The MCP endpoint: bearer auth and the 401 that starts sign-in, the
JSON-RPC surface, and the tools acting as the token's user."""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.case.models import Fact
from apps.mcp.models import McpToken
from apps.mcp.tools import TOOLS
from apps.tasks.models import Task

from .conftest import rpc

pytestmark = pytest.mark.django_db


def result(response):
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["jsonrpc"] == "2.0" and body["id"] == 1
    assert "error" not in body, body
    return body["result"]


def call(token, tool, **arguments):
    return result(rpc(token, "tools/call", {"name": tool, "arguments": arguments}))


def text(outcome):
    assert outcome["isError"] is False, outcome
    return outcome["content"][0]["text"]


class TestAuth:
    def test_no_token_is_401_pointing_at_the_metadata(self):
        response = rpc(None, "initialize")
        assert response.status_code == 401
        header = response["WWW-Authenticate"]
        assert header.startswith("Bearer ")
        assert (
            'resource_metadata="http://testserver/.well-known/oauth-protected-resource/mcp"'
            in header
        )
        assert "invalid_token" not in header

    def test_bad_token_is_401_invalid_token(self):
        response = rpc("kma_nothing", "initialize")
        assert response.status_code == 401
        assert 'error="invalid_token"' in response["WWW-Authenticate"]

    def test_expired_token_is_401(self, access_token):
        McpToken.objects.update(access_expires_at=timezone.now() - timedelta(seconds=1))
        assert rpc(access_token, "ping").status_code == 401

    def test_revoked_connection_is_401(self, access_token, connection):
        connection.delete()
        assert rpc(access_token, "ping").status_code == 401

    def test_inactive_user_is_401(self, access_token, user):
        user.is_active = False
        user.save()
        assert rpc(access_token, "ping").status_code == 401

    def test_api_token_is_not_a_bearer(self, user):
        from apps.accounts.models import ApiToken

        assert rpc(ApiToken.for_user(user).key, "ping").status_code == 401

    def test_get_is_405(self, access_token):
        response = Client().get("/mcp", HTTP_AUTHORIZATION=f"Bearer {access_token}")
        assert response.status_code == 405
        assert response["Allow"] == "POST"

    def test_foreign_origin_is_403(self, access_token):
        response = rpc(access_token, "ping", HTTP_ORIGIN="https://evil.example.com")
        assert response.status_code == 403

    def test_own_origin_passes(self, access_token):
        assert (
            rpc(access_token, "ping", HTTP_ORIGIN="http://testserver").status_code
            == 200
        )

    def test_use_is_recorded(self, access_token, connection):
        assert connection.last_used_at is None
        rpc(access_token, "ping")
        connection.refresh_from_db()
        assert connection.last_used_at is not None


class TestProtocol:
    def test_initialize_echoes_a_supported_version(self, access_token):
        body = result(
            rpc(
                access_token,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "claude-ai", "version": "1"},
                },
            )
        )
        assert body["protocolVersion"] == "2025-06-18"
        assert body["serverInfo"]["name"] == "kosmos"
        assert "tools" in body["capabilities"]
        assert "find_matter" in body["instructions"]

    def test_initialize_offers_the_latest_for_an_unknown_version(self, access_token):
        body = result(
            rpc(access_token, "initialize", {"protocolVersion": "1999-01-01"})
        )
        assert body["protocolVersion"] == "2025-11-25"

    def test_unsupported_version_header_is_400(self, access_token):
        response = rpc(access_token, "ping", HTTP_MCP_PROTOCOL_VERSION="1999-01-01")
        assert response.status_code == 400

    def test_supported_version_header_passes(self, access_token):
        response = rpc(access_token, "ping", HTTP_MCP_PROTOCOL_VERSION="2025-06-18")
        assert response.status_code == 200

    def test_notification_is_202_with_no_body(self, access_token):
        response = rpc(access_token, "notifications/initialized", message_id=None)
        assert response.status_code == 202
        assert response.content == b""

    def test_ping(self, access_token):
        assert result(rpc(access_token, "ping")) == {}

    def test_unknown_method(self, access_token):
        body = rpc(access_token, "resources/read", {"uri": "x"}).json()
        assert body["error"]["code"] == -32601

    def test_empty_prompts_and_resources(self, access_token):
        assert result(rpc(access_token, "prompts/list")) == {"prompts": []}
        assert result(rpc(access_token, "resources/list")) == {"resources": []}

    def test_parse_error(self, access_token):
        response = Client().post(
            "/mcp",
            "{not json",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == -32700

    def test_batch_is_refused(self, access_token):
        response = Client().post(
            "/mcp",
            '[{"jsonrpc": "2.0", "id": 1, "method": "ping"}]',
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == -32600

    def test_tools_list(self, access_token):
        listed = result(rpc(access_token, "tools/list"))["tools"]
        assert [t["name"] for t in listed] == [t.name for t in TOOLS]
        read_matter = next(t for t in listed if t["name"] == "read_matter")
        assert read_matter["inputSchema"]["required"] == ["matter_id", "section"]
        assert "ledger" in read_matter["inputSchema"]["properties"]["section"]["enum"]
        assert read_matter["annotations"]["readOnlyHint"] is True
        add_task = next(t for t in listed if t["name"] == "add_task")
        assert add_task["annotations"]["readOnlyHint"] is False


class TestTools:
    def test_find_matter(self, access_token, matter):
        outcome = call(access_token, "find_matter", query="test")
        assert text(outcome) == f"- [id {matter.id}] Test Matter"

    def test_find_matter_no_match(self, access_token, matter):
        assert "No open matters" in text(call(access_token, "find_matter", query="zzz"))

    def test_read_matter_overview(self, access_token, matter):
        outcome = call(
            access_token, "read_matter", matter_id=matter.id, section="overview"
        )
        assert "Test Matter" in text(outcome)

    def test_read_matter_refusal_is_a_tool_error(self, access_token, matter):
        outcome = call(
            access_token, "read_matter", matter_id=matter.id, section="bogus"
        )
        assert outcome["isError"] is True
        assert "Kosmos API error (400)" in outcome["content"][0]["text"]

    def test_denied_matter_is_a_tool_error(self, oauth_client, matter):
        from apps.accounts.models import CustomUser
        from apps.mcp.models import McpConnection

        outsider = CustomUser.objects.create(
            username="outsider", email="outsider@example.com", perm_all_matters=False
        )
        connection = McpConnection.objects.create(user=outsider, client=oauth_client)
        token, _, _ = McpToken.issue(connection)
        outcome = call(token, "read_matter", matter_id=matter.id, section="overview")
        assert outcome["isError"] is True
        assert "(404)" in outcome["content"][0]["text"]

    def test_money_needs_financial_permission(self, access_token, matter, user):
        user.perm_financial = False
        user.save()
        outcome = call(
            access_token, "read_matter", matter_id=matter.id, section="ledger"
        )
        assert outcome["isError"] is True
        assert "(403)" in outcome["content"][0]["text"]

    def test_read_document(self, access_token, document):
        document.ocr_text = "Full extracted document text."
        document.save(update_fields=["ocr_text"])
        outcome = call(access_token, "read_document", document_id=document.id)
        assert "Full extracted document text." in text(outcome)

    def test_search_kosmos(self, access_token, matter):
        outcome = call(
            access_token, "search_kosmos", query="Test Matter", scope="matters"
        )
        assert f"[matter:{matter.id}]" in text(outcome)

    def test_add_fact(self, access_token, matter, highlight):
        outcome = call(
            access_token,
            "add_fact",
            matter_id=matter.id,
            description="Contract signed by both parties",
            date="2024-03-01",
            highlight_ids=[highlight.id],
        )
        assert text(outcome).startswith("- Added to timeline:")
        fact = Fact.objects.get(description="Contract signed by both parties")
        assert list(fact.highlights.all()) == [highlight]

    def test_add_task_as_the_user(self, access_token, matter, user):
        outcome = call(
            access_token,
            "add_task",
            description="serve the subpoena",
            matter_id=matter.id,
            due="2026-09-01",
        )
        assert "[Test Matter]" in text(outcome)
        task = Task.objects.get(description__icontains="serve the subpoena")
        assert task.user == user and task.matter == matter

    def test_add_witness_dedups(self, access_token, matter):
        first = call(
            access_token, "add_witness", matter_id=matter.id, name="Dana Whitfield"
        )
        assert "Added witness" in text(first)
        again = call(
            access_token, "add_witness", matter_id=matter.id, name="dana whitfield"
        )
        assert "Already on the witness list" in text(again)

    def test_unknown_tool_is_invalid_params(self, access_token):
        body = rpc(access_token, "tools/call", {"name": "drop_tables"}).json()
        assert body["error"]["code"] == -32602

    def test_missing_argument_is_invalid_params(self, access_token):
        body = rpc(
            access_token, "tools/call", {"name": "read_matter", "arguments": {}}
        ).json()
        assert body["error"]["code"] == -32602
        assert "matter_id" in body["error"]["message"]

    def test_wrong_argument_type_is_invalid_params(self, access_token):
        body = rpc(
            access_token,
            "tools/call",
            {
                "name": "read_matter",
                "arguments": {"matter_id": "abc", "section": "overview"},
            },
        ).json()
        assert body["error"]["code"] == -32602
