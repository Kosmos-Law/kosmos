"""Matters and their proceedings as structured JSON, for programs that
keep their own copy of them: Kosmos Discover links its matters to these
and refreshes its copy whenever one of its pages opens. Read-only, and limited
to the matters the caller's user may see (of any status: a linked matter
that closes here has to be seen to close there).

Two credentials are taken. A bearer token from the OAuth server in
apps/mcp, issued for this API as its ``resource``: how Discover connects
(an admin there signs in to Kosmos and clicks Allow), and good for
nothing else in Kosmos. Or the user's X-Kosmos-Token, like the other JSON
APIs.

The matter API in apps/ai/api.py answers in text for a model to read;
this one answers in fields.
"""

from functools import wraps

from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from apps.accounts.access import filter_matters_for_user
from apps.accounts.api_auth import kosmos_api_auth
from apps.matters.models import Matter
from apps.matters.proceedings.models import Proceeding
from apps.mcp.models import RESOURCE_MATTERS, McpToken

MATTER_404 = "No such matter, or you do not have access to it."
BEARER_401 = (
    "The access token is expired, revoked, or not for the matters API. "
    "Refresh it, or connect to Kosmos again."
)


def matters_api_auth(view):
    """Bearer or X-Kosmos-Token; sets request.api_user either way. A
    request that sends ``Authorization: Bearer`` is judged on that alone:
    the token must be live, its user active, and its connection one that
    was authorized for this API (a Claude connection's token is not)."""
    with_api_token = kosmos_api_auth(view)

    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer":
            return with_api_token(request, *args, **kwargs)
        connection = McpToken.by_access_token(token.strip(), RESOURCE_MATTERS)
        if connection is None:
            response = JsonResponse({"error": BEARER_401}, status=401)
            response["WWW-Authenticate"] = 'Bearer error="invalid_token"'
            return response
        connection.touch()
        request.api_user = connection.user
        return view(request, *args, **kwargs)

    return wrapper


def _date(value):
    return value.isoformat() if value else None


def matter_fields(matter, request):
    """One matter as the API gives it. ``url`` is its page here."""
    return {
        "id": matter.id,
        "name": matter.name or "",
        "status": matter.status or "",
        "description": matter.description or "",
        "client": matter.client.name if matter.client else "",
        "client_reference_id": matter.client_reference_id or "",
        "jurisdiction": matter.jurisdiction or "",
        "practice_area": matter.practice_area.name if matter.practice_area else "",
        "date_start": _date(matter.date_start),
        "date_end": _date(matter.date_end),
        "updated_at": _date(matter.updated_at),
        "url": request.build_absolute_uri(reverse("matters:detail", args=[matter.id])),
    }


def proceeding_fields(proceeding):
    return {
        "id": proceeding.id,
        "forum": proceeding.forum or "",
        "case_number": proceeding.case_number or "",
        "nickname": proceeding.nickname or "",
        "date_filed": _date(proceeding.date_filed),
        "status": proceeding.status or "",
        "primary": proceeding.primary,
    }


def _matters(user):
    return filter_matters_for_user(
        Matter.objects.select_related("client", "practice_area"), user
    )


@matters_api_auth
@require_GET
def api_matters(request):
    """The matters the caller's user may see, by name. ``?q=`` narrows by
    name, client or client reference; ``?status=`` (repeatable) by status.
    ``user`` says whose matters these are, for a program that shows who
    it is connected as."""
    matters = _matters(request.api_user)
    q = (request.GET.get("q") or "").strip()
    if q:
        matters = matters.filter(
            Q(name__icontains=q)
            | Q(client__name__icontains=q)
            | Q(client_reference_id__icontains=q)
        )
    statuses = [s for s in request.GET.getlist("status") if s]
    if statuses:
        matters = matters.filter(status__in=statuses)
    user = request.api_user
    return JsonResponse(
        {
            "user": {
                "name": user.get_full_name() or user.username,
                "email": user.email or "",
            },
            "matters": [
                matter_fields(matter, request)
                for matter in matters.order_by("name", "id")
            ],
        }
    )


@matters_api_auth
@require_GET
def api_matter(request, matter_id):
    """One matter and its proceedings, the primary one first."""
    matter = _matters(request.api_user).filter(pk=matter_id).first()
    if matter is None:
        return JsonResponse({"error": MATTER_404}, status=404)
    proceedings = Proceeding.objects.filter(matter=matter).order_by(
        "-primary", "date_filed", "id"
    )
    return JsonResponse(
        {
            "matter": matter_fields(matter, request),
            "proceedings": [proceeding_fields(p) for p in proceedings],
        }
    )
