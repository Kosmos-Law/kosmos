"""Shared pieces of the Kosmos JSON APIs (the matter API in apps/ai/api.py,
the calendar and search APIs): the X-Kosmos-Token check and the error the
service functions behind them raise. Lives with ApiToken so every consumer
can import it without pulling in another app's view machinery.
"""

from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import ApiToken

TOKEN_HELP = (
    "Invalid or missing Kosmos token. "
    "Visit the Claude page in Kosmos settings to issue a new one."
)


class ApiError(Exception):
    """A refusal with an HTTP status and a message. The JSON views answer it
    as ``{"error": message}`` with that status; the MCP server's tools relay
    the message to the model as a tool error."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def kosmos_api_auth(view):
    """Token auth for the JSON APIs; sets request.api_user.

    Same X-Kosmos-Token contract as companion_auth, kept separate so this
    401 body can be actionable without touching the .oxt client contract.
    Inactive users are rejected: revoking a login must also revoke this.
    """

    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        key = request.headers.get("X-Kosmos-Token", "")
        token = (
            ApiToken.objects.select_related("user").filter(key=key).first()
            if key
            else None
        )
        if token is None or not token.user.is_active:
            return JsonResponse({"error": TOKEN_HELP}, status=401)
        request.api_user = token.user
        return view(request, *args, **kwargs)

    return wrapper
