import re

from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
)


class HtmxLoginRedirectMiddleware:
    """Redirect HTMX requests from logged-out users to the login page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (
            not request.user.is_authenticated
            and request.headers.get("HX-Request") == "true"
            and response.status_code == 302
        ):
            redirect_url = response.get("Location", "/accounts/login/")
            resp = HttpResponse(status=200)
            resp["HX-Redirect"] = redirect_url
            return resp

        return response


class PermissionMiddleware:
    """Block paths based on user permissions for non-admin users."""

    PERMISSION_PATHS = [
        ("/invoicing/", "perm_financial"),
        ("/intakes/", "perm_intakes"),
        ("/settings/intake-emails/", "perm_intakes"),
        ("/reports/", "perm_reports"),
    ]

    # The same gates for pages whose path starts with a matter id. Hiding
    # the tab in the navigation is not a gate: the URL has to refuse too.
    PERMISSION_PATTERNS = [
        (re.compile(r"^/matters/\d+/(rates|ledger)(/|$)"), "perm_financial"),
        # Saved case law (a view of the AI tab) and the case viewer need the
        # Research permission, under /case/<matter>/caselaws/,
        # /case/caselaws/<case>/ and /case/<matter>/viewer/cluster/<id>/.
        (
            re.compile(
                r"^/case/(\d+/)?(tab/)?caselaws/"
                r"|^/case/\d+/viewer/cluster/"
            ),
            "perm_research",
        ),
    ]

    # Pages that exist only when an optional integration is set up. Hidden
    # links are not a gate: without the integration these 404 for everyone.
    AI_PATTERN = re.compile(
        r"^/case/(\d+/)?(tab/)?ai/"
        r"|^/case/drafts/"
        r"|^/intakes/\d+/(assess|chat/)"
        r"|^/settings/tasks/"
    )
    CASELAW_PATTERN = re.compile(
        r"^/case/(\d+/)?(tab/)?caselaws/|^/case/\d+/viewer/cluster/"
    )

    # Where matter membership is enforced from the URL alone. /matters/ and
    # /notes/ views carry their own checks.
    MATTER_SCOPED_PREFIXES = ("/case/",)

    # Paths only admins may access (page + all its endpoints), regardless of perms.
    ADMIN_ONLY_PATHS = [
        "/settings/users/",
        "/settings/permissions/",
        "/settings/firm/",
        "/settings/contacts/",
        "/settings/matters/",
        "/settings/tasks/",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self.AI_PATTERN.match(request.path):
            from apps.settings.ai import ai_enabled

            if not ai_enabled():
                return HttpResponseNotFound()
        if self.CASELAW_PATTERN.match(request.path):
            from apps.case.courtlistener import get_api_token

            if not get_api_token():
                return HttpResponseNotFound()

        if request.user.is_authenticated and not request.user.is_admin:
            if any(request.path.startswith(p) for p in self.ADMIN_ONLY_PATHS):
                return HttpResponseForbidden()

            for path_prefix, perm_field in self.PERMISSION_PATHS:
                if request.path.startswith(path_prefix) and not getattr(
                    request.user, perm_field
                ):
                    return HttpResponseForbidden()

            for pattern, perm_field in self.PERMISSION_PATTERNS:
                if pattern.match(request.path) and not getattr(
                    request.user, perm_field
                ):
                    return HttpResponseForbidden()

        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """A user limited to assigned matters gets nothing from another
        matter's case workspace, whichever id the URL names it by."""
        from apps.accounts.access import user_may_use_route

        if (
            request.user.is_authenticated
            and request.path.startswith(self.MATTER_SCOPED_PREFIXES)
            and not user_may_use_route(request.user, view_kwargs)
        ):
            return HttpResponseForbidden()
        return None


class AuthenticatorRequiredMiddleware:
    """When the firm requires an authenticator app, a signed-in user who has
    none can only reach Settings > Security (to set it up) and sign out.
    Everything else sends them there, HTMX requests by HX-Redirect."""

    SETUP_PATH = "/settings/security/"
    EXEMPT_PREFIXES = (SETUP_PATH, "/accounts/", "/static/", "/media/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not request.path.startswith(
            self.EXEMPT_PREFIXES
        ):
            from apps.settings.models import Firm

            firm = Firm.objects.only("require_authenticator").first()
            if (
                firm
                and firm.require_authenticator
                and not request.user.has_authenticator
            ):
                if request.headers.get("HX-Request") == "true":
                    response = HttpResponse(status=200)
                    response["HX-Redirect"] = self.SETUP_PATH
                    return response
                return HttpResponseRedirect(self.SETUP_PATH)
        return self.get_response(request)
