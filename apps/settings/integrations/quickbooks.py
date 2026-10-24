"""Settings > Integrations > QuickBooks Online: connecting the firm's
company for Books to mirror, and disconnecting it.

Admin-only, and only while Books is on (the middleware 404s the paths
otherwise). The flow is the Google one's: Connect sends the administrator
to Intuit with a state kept in the session, Intuit sends them back to
/settings/quickbooks/store, and a callback whose state this session did
not issue is refused. The real work is apps/books/intuit.py.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.books import intuit
from apps.settings.integrations import PENDING_TOAST_KEY

logger = logging.getLogger(__name__)

STATE_KEY = "quickbooks_state"

NOT_CONFIGURED_MSG = (
    "QuickBooks sign-in isn't set up on this server yet, so QuickBooks can't "
    "be connected. An administrator needs to set the app's keys in config/.env "
    "first."
)


def context():
    """What the Integrations page shows for QuickBooks."""
    return {
        "quickbooks": {
            "configured": intuit.configured(),
            "sandbox": intuit.environment() == intuit.QuickBooksConnection.SANDBOX,
            "connection": intuit.connection(),
        }
    }


def _back(request, kind, message):
    request.session[PENDING_TOAST_KEY] = {"type": kind, "message": message}
    return redirect("settings:integrations-index")


@login_required
def connect(request):
    if not request.user.is_admin:
        return HttpResponseForbidden()
    if not intuit.configured():
        return _back(request, "error", NOT_CONFIGURED_MSG)
    state = intuit.new_state()
    request.session[STATE_KEY] = state
    return redirect(intuit.authorize_url(intuit.redirect_uri(request), state))


@login_required
def store(request):
    state = request.session.pop(STATE_KEY, None)
    if not state or request.GET.get("state") != state:
        return HttpResponseBadRequest(
            "This QuickBooks connection was not started from this session. "
            "Go back to Settings, Integrations and connect again."
        )
    if not request.user.is_admin:
        return HttpResponseForbidden()
    if request.GET.get("error"):
        # The administrator cancelled on Intuit's side, or Intuit refused.
        return _back(request, "error", "QuickBooks was not connected.")
    code = request.GET.get("code")
    realm_id = request.GET.get("realmId")
    if not code or not realm_id:
        return HttpResponseBadRequest("Intuit sent no code or company.")
    try:
        conn = intuit.connect(
            code, realm_id, intuit.redirect_uri(request), user=request.user
        )
    except intuit.QuickBooksError as exc:
        logger.warning("QuickBooks connect failed: %s", exc)
        return _back(request, "error", f"QuickBooks could not be connected: {exc}")
    name = conn.company_name or "the company"
    return _back(request, "success", f"QuickBooks connected: {name}")


@login_required
@require_POST
def disconnect(request):
    if not request.user.is_admin:
        return HttpResponseForbidden()
    intuit.disconnect()
    return _back(request, "success", "QuickBooks disconnected")
