import json
import logging

import google_auth_oauthlib.flow
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from googleapiclient.discovery import build

import apps.drive.google as drive_google
import apps.mail.google as mail_google
from apps.mail.models import GmailAccount
from apps.settings.integrations.oauth import google_oauth_configured
from utils.prepare_path import prepare_path
from utils.toasts import toast_success

logger = logging.getLogger(__name__)

CONTACTS_TOKEN_PATH = settings.GOOGLE_CONTACTS_TOKEN_PATH
CALENDAR_TOKEN_PATH = settings.GOOGLE_CALENDAR_TOKEN_PATH
DRIVE_TOKEN_PATH = settings.GOOGLE_DRIVE_TOKEN_PATH
EMAIL_TOKEN_PATH = settings.GOOGLE_EMAIL_TOKEN_PATH
GOOGLE_TOKEN_PATH = settings.GOOGLE_CLIENT_SECRET_PATH

# Map the <app> URL segment to its token file.
TOKEN_PATHS = {
    "contacts": CONTACTS_TOKEN_PATH,
    "calendar": CALENDAR_TOKEN_PATH,
    "drive": DRIVE_TOKEN_PATH,
    "email": EMAIL_TOKEN_PATH,
}

# A toast for the next load of the Integrations page, left by a view that
# redirected there (a full-page redirect carries no HX toast header).
PENDING_TOAST_KEY = "integrations_pending_toast"

GOOGLE_OAUTH_MISSING_MSG = (
    "Google sign-in isn't set up on this server yet, so Google can't be "
    "connected. An administrator needs to add the OAuth client file first."
)


def _token_exists(file_path):
    prepare_path(file_path)

    try:
        with open(file_path, "r") as file:
            data = json.load(file)

        return "token" in data
    except (IOError, json.JSONDecodeError):
        return False


def _get_redirect_uri(request):
    return f"https://{request.get_host()}/settings/google/store"


def _create_flow(redirect_uri, state=None):
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        GOOGLE_TOKEN_PATH,
        state=state,
        scopes=[
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/contacts",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/gmail.readonly",
            # Label create/rename only — message content stays read-only.
            # Lets the sync provision each mailbox's matter labels so users
            # only ever *apply* labels, never build the taxonomy.
            "https://www.googleapis.com/auth/gmail.labels",
        ],
    )

    flow.redirect_uri = redirect_uri
    return flow


def _get_auth_url(flow):
    return flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )


def _visible_gmail_accounts(user, gmail_status):
    """The mailboxes whose sync health the page shows: every one for an
    administrator, who looks after the firm's connections, and only their
    own for anyone else."""
    accounts = gmail_status["accounts"] if gmail_status else []
    if user.is_admin:
        return accounts
    return [account for account in accounts if account.user_id == user.id]


@login_required
def index(request):
    contacts_token = _token_exists(CONTACTS_TOKEN_PATH)
    calendar_token = _token_exists(CALENDAR_TOKEN_PATH)
    drive_token = _token_exists(DRIVE_TOKEN_PATH)
    # Email is per-user (GmailAccount rows), not a shared token file.
    email_token = mail_google.check_credentials()

    # Drive case-notes sync health (last sync, synced count, unmatched folders).
    drive_status = drive_google.get_sync_status() if drive_token else None
    # Gmail case-email sync health (per-account last sync, missing labels).
    gmail_status = mail_google.get_sync_status() if email_token else None

    context = {
        "app": "settings",
        "subapp": "integrations",
        "contacts_token": contacts_token,
        "calendar_token": calendar_token,
        "drive_token": drive_token,
        "drive_status": drive_status,
        "email_token": email_token,
        "gmail_status": gmail_status,
        "own_gmail_account": GmailAccount.objects.filter(user=request.user).first(),
        "gmail_accounts": _visible_gmail_accounts(request.user, gmail_status),
        # A missing label is named after its matter. Someone limited to
        # assigned matters is told how many, not which.
        "show_label_names": request.user.is_admin or request.user.perm_all_matters,
        "label_root": settings.GMAIL_LABEL_ROOT,
        # Without the OAuth client file every Connect would fail, so the
        # page offers none and says why instead.
        "google_oauth_ready": google_oauth_configured(),
        "pending_toast": request.session.pop(PENDING_TOAST_KEY, None),
    }
    if request.user.is_admin:
        context.update(_ai_context())

    return render(request, "settings/integrations/index.html", context)


def _forbidden_for(request, app):
    """Shared-token integrations (firm-wide files) are admin-only; email is
    per-user, so any signed-in user may connect their own mailbox."""
    return app != "email" and not request.user.is_admin


@login_required
def google_login(request, app):
    if _forbidden_for(request, app):
        return HttpResponseForbidden()
    if not google_oauth_configured():
        # Reached from a stale page or a typed address: say why, don't 500.
        request.session[PENDING_TOAST_KEY] = {
            "type": "error",
            "message": GOOGLE_OAUTH_MISSING_MSG,
        }
        return redirect("settings:integrations-index")
    redirect_uri = _get_redirect_uri(request)

    # Create OAuth2 flow instance
    flow = _create_flow(redirect_uri)

    authorization_url, state = _get_auth_url(flow)

    # Store the state to prevent CSRF attacks
    request.session["state"] = state
    request.session["app"] = app

    return redirect(authorization_url)


@login_required
def google_store(request):
    # Google sends back the state this session was given when it started the
    # connection. A callback without that state did not start here (someone
    # else's link, or a stale one), and its account must not be connected.
    state = request.session.pop("state", None)
    app = request.session.pop("app", None)
    if not state or not app or request.GET.get("state") != state:
        return HttpResponseBadRequest(
            "This Google connection was not started from this session. "
            "Go back to Settings, Integrations and connect again."
        )
    if _forbidden_for(request, app):
        return HttpResponseForbidden()

    redirect_uri = _get_redirect_uri(request)

    # Create OAuth2 flow instance
    flow = _create_flow(redirect_uri, state=state)

    authorization_response = request.build_absolute_uri()
    flow.fetch_token(authorization_response=authorization_response)

    google_credentials = flow.credentials.to_json()

    if app == "email":
        # Per-user mailbox: the token lands on the requester's GmailAccount,
        # not the shared token file. The address comes from the mailbox
        # itself (getProfile), so sent mail can be recognized as "ours".
        service = build("gmail", "v1", credentials=flow.credentials)
        profile = service.users().getProfile(userId="me").execute()
        GmailAccount.objects.update_or_create(
            user=request.user,
            defaults={
                "address": profile.get("emailAddress", ""),
                "token": google_credentials,
                # Fresh token, fresh mailbox view: force a bootstrap.
                "history_id": None,
            },
        )
        return redirect("/settings/integrations/")

    path = TOKEN_PATHS.get(app, CALENDAR_TOKEN_PATH)

    prepare_path(path)
    with open(path, "w") as file:
        file.write(google_credentials)

    # On (re)connecting the calendar, flush any local events that weren't synced
    # while disconnected — adopting existing Pending events on first connect and
    # clearing the backlog after a token outage.
    if app == "calendar":
        from apps.calendar import sync

        sync.reconcile()

    return redirect("/settings/integrations/")


@login_required
@require_POST
def google_logout(request, app):
    if _forbidden_for(request, app):
        return HttpResponseForbidden()
    if app == "email":
        # Disconnect the requester's own mailbox. Cascades that mailbox's
        # Email rows; messages a colleague's mailbox also holds stay visible
        # through their rows (promoted Documents are never touched).
        GmailAccount.objects.filter(user=request.user).delete()
        return redirect("/settings/integrations/")

    path = TOKEN_PATHS.get(app, CALENDAR_TOKEN_PATH)

    prepare_path(path)
    with open(path, "w") as file:
        file.write("")

    return redirect("/settings/integrations/")


# ── AI providers ─────────────────────────────────────────────────────────────


def _ai_context(firm=None, errors=None):
    from apps.settings import ai

    firm = firm if firm is not None else _firm_or_new()
    return {
        "ai_providers": [
            {
                "id": provider,
                "label": ai.PROVIDER_LABELS[provider],
                "source": ai.key_source(provider, firm),
                "error": (errors or {}).get(provider, ""),
            }
            for provider in (ai.GEMINI, ai.ANTHROPIC)
        ],
    }


def _firm_or_new():
    from apps.settings.models import Firm

    return Firm.objects.first() or Firm.objects.create(name="")


def verify_ai_key(provider, key):
    """None when ``key`` works for ``provider``, else a short reason. Lists
    the provider's models, which costs nothing."""
    from apps.settings import ai

    try:
        if provider == ai.GEMINI:
            from google import genai

            next(iter(genai.Client(api_key=key).models.list()), None)
        else:
            import anthropic

            anthropic.Anthropic(api_key=key).models.list(limit=1)
    except Exception as exc:
        logger.info("AI key check failed for %s: %s", provider, exc)
        return "The provider rejected this key. Check it and try again."
    return None


@login_required
@require_POST
def ai_key_save(request, provider):
    """Save (or, with an empty value, remove) an admin-entered AI key."""
    from apps.settings import ai

    if not request.user.is_admin:
        return HttpResponseForbidden()
    if provider not in ai.PROVIDER_LABELS:
        return HttpResponseBadRequest()
    firm = _firm_or_new()
    field = f"{provider}_api_key"
    key = request.POST.get("key", "").strip()
    label = ai.PROVIDER_LABELS[provider]

    if key:
        error = verify_ai_key(provider, key)
        if error:
            return render(
                request,
                "settings/integrations/ai.html",
                _ai_context(firm, {provider: error}),
            )
        setattr(firm, field, ai.encrypt_key(key))
        message = f"{label} connected"
    else:
        setattr(firm, field, "")
        message = f"{label} key removed"
    firm.save(update_fields=[field])

    response = render(request, "settings/integrations/ai.html", _ai_context(firm))
    toast_success(response, message)
    return response
