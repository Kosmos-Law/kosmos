"""Shared token auth for the Kosmos JSON APIs behind the Claude Desktop
MCP server (the matter API in apps/ai/api.py, the calendar and search
APIs). Lives with ApiToken so every
consumer can import it without pulling in another app's view machinery.
"""

from functools import wraps

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import ApiToken

TOKEN_HELP = (
    "Invalid or missing Kosmos token. "
    "Visit the Claude Desktop page in Kosmos settings to issue a new one."
)


def kosmos_api_auth(view):
    """Token auth for the MCP-facing APIs; sets request.api_user.

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
