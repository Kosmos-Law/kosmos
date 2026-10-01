import re

from django.http import HttpResponse, HttpResponseForbidden


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
        (re.compile(r"^/case/(\d+/)?research/"), "perm_research"),
    ]

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
        if request.user.is_authenticated and not request.user.is_admin:
            if request.path.startswith("/admin/"):
                return HttpResponseForbidden()

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
