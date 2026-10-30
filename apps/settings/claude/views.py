"""Settings > Claude: connect Claude to Kosmos, see what is connected,
disconnect it.

Claude connects over the remote MCP server (apps/mcp): the page shows the
one URL to paste into Claude's connector settings, and the sign-in that
follows happens in the browser, on Kosmos's own consent screen. The
connections listed here are McpConnection rows; Disconnect deletes one,
which ends its tokens at once.

The page also keeps the user's API token (ApiToken), which the LibreOffice
companion and the token-authenticated JSON APIs use: issue, rotate and
revoke. It has nothing to do with the Claude connection any more, but this
is where users know to find it.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import ApiToken
from apps.mcp.models import McpConnection
from apps.mcp.oauth import mcp_url


@login_required
def claude_index(request):
    context = {
        "subapp": "claude",
        "connector_url": mcp_url(request),
        "connections": McpConnection.objects.filter(user=request.user).select_related(
            "client"
        ),
        "token": ApiToken.objects.filter(user=request.user).first(),
    }
    return render(request, "settings/claude/index.html", context)


@login_required
@require_POST
def claude_disconnect(request, connection_id):
    """End one connection. Its tokens stop working at once; Claude shows
    the connector as needing sign-in."""
    connection = get_object_or_404(McpConnection, pk=connection_id, user=request.user)
    connection.delete()
    return redirect("settings:claude-index")


@login_required
@require_POST
def claude_rotate(request):
    """Generate (or re-key) the user's API token. Serves both buttons: the
    delete is a no-op when no token exists yet."""
    ApiToken.objects.filter(user=request.user).delete()
    ApiToken.for_user(request.user)
    return redirect("settings:claude-index")


@login_required
@require_POST
def claude_revoke(request):
    ApiToken.objects.filter(user=request.user).delete()
    return redirect("settings:claude-index")
