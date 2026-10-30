"""The MCP endpoint: ``POST /mcp``, streamable HTTP, stateless.

Every request is one JSON-RPC message answered with one JSON object (the
transport allows a server to answer with ``application/json`` instead of
opening an event stream; nothing here streams, and there is no session,
so no ``Mcp-Session-Id`` is issued). ``GET`` is refused with 405, as the
transport provides for a server that has no stream to offer.

Authentication is a bearer token from apps/mcp/oauth.py. A request
without one, or with one that has expired or been revoked, is answered
401 with a ``WWW-Authenticate`` header naming the protected resource
metadata: that header is what sends Claude into the sign-in flow. The
tools run as the token's user.
"""

import json
import logging
from urllib.parse import urlsplit

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from . import tools
from .models import McpToken
from .oauth import resource_metadata_url

logger = logging.getLogger(__name__)

PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")
SERVER_INFO = {"name": "kosmos", "title": "Kosmos", "version": "1.0"}

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


class RpcError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _unauthorized(request, description=None):
    challenge = (
        f'Bearer realm="Kosmos", resource_metadata="{resource_metadata_url(request)}"'
    )
    if description:
        challenge += f', error="invalid_token", error_description="{description}"'
    response = JsonResponse(
        {
            "error": "invalid_token" if description else "unauthorized",
            "error_description": description or "Sign in to Kosmos to connect.",
        },
        status=401,
    )
    response["WWW-Authenticate"] = challenge
    return response


def _bearer(request):
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def _rpc_response(message_id, result=None, error=None, status=200):
    body = {"jsonrpc": "2.0", "id": message_id}
    if error is not None:
        body["error"] = {"code": error.code, "message": error.message}
    else:
        body["result"] = result
    return JsonResponse(body, status=status)


def _origin_allowed(request):
    """DNS-rebinding guard the transport asks for: a browser-sent Origin
    must be this host. Claude's servers send none."""
    origin = request.headers.get("Origin")
    if not origin:
        return True
    return urlsplit(origin).netloc.lower() == request.get_host().lower()


@csrf_exempt
def endpoint(request):
    if request.method != "POST":
        response = HttpResponse(status=405)
        response["Allow"] = "POST"
        return response
    if not _origin_allowed(request):
        return HttpResponse(status=403)

    token = _bearer(request)
    if token is None:
        return _unauthorized(request)
    connection = McpToken.by_access_token(token)
    if connection is None:
        return _unauthorized(request, "The token is expired or revoked.")

    version = request.headers.get("MCP-Protocol-Version")
    if version and version not in PROTOCOL_VERSIONS:
        return JsonResponse(
            {"error": f"Unsupported MCP-Protocol-Version {version}."}, status=400
        )

    try:
        message = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _rpc_response(
            None, error=RpcError(PARSE_ERROR, "Parse error"), status=400
        )
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _rpc_response(
            None,
            error=RpcError(INVALID_REQUEST, "Expected one JSON-RPC 2.0 message"),
            status=400,
        )

    # A notification, or a response to something this server never asks
    # (it makes no requests of the client): accepted and done.
    if "id" not in message or "method" not in message:
        return HttpResponse(status=202)

    connection.touch()
    user = connection.user
    params = message.get("params") or {}
    try:
        result = _dispatch(message["method"], params, user)
    except RpcError as exc:
        return _rpc_response(message["id"], error=exc)
    return _rpc_response(message["id"], result=result)


def _dispatch(method, params, user):
    if not isinstance(params, dict):
        raise RpcError(INVALID_PARAMS, "params must be an object")
    if method == "initialize":
        requested = params.get("protocolVersion")
        return {
            "protocolVersion": requested
            if requested in PROTOCOL_VERSIONS
            else PROTOCOL_VERSIONS[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": tools.INSTRUCTIONS,
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [tool.listing() for tool in tools.TOOLS]}
    if method == "tools/call":
        return _call_tool(params, user)
    if method in ("resources/list", "resources/templates/list", "prompts/list"):
        key = (
            "resourceTemplates"
            if method == "resources/templates/list"
            else method.split("/")[0]
        )
        return {key: []}
    raise RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")


def _call_tool(params, user):
    name = params.get("name")
    tool = tools.TOOLS_BY_NAME.get(name)
    if tool is None:
        raise RpcError(INVALID_PARAMS, f"Unknown tool: {name}")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise RpcError(INVALID_PARAMS, "arguments must be an object")
    try:
        text = tool.run(user, arguments)
    except tools.InvalidArguments as exc:
        raise RpcError(INVALID_PARAMS, str(exc))
    except tools.ToolError as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    except Exception:
        logger.exception("MCP tool %s failed for user %s", name, user.pk)
        return {
            "content": [
                {"type": "text", "text": f"The {name} tool failed inside Kosmos."}
            ],
            "isError": True,
        }
    return {"content": [{"type": "text", "text": text}], "isError": False}
