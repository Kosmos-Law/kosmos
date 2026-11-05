"""Matters and their proceedings as structured JSON, for programs that
keep their own copy of them: Kosmos Discover links its matters to these
and refreshes its copy whenever one of its pages opens. Read-only, behind
the X-Kosmos-Token check, and limited to the matters the token's user may
see (of any status: a linked matter that closes here has to be seen to
close there).

The matter API in apps/ai/api.py answers in text for a model to read;
this one answers in fields.
"""

from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.accounts.access import filter_matters_for_user
from apps.accounts.api_auth import kosmos_api_auth
from apps.matters.models import Matter
from apps.matters.proceedings.models import Proceeding

MATTER_404 = "No such matter, or you do not have access to it."


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


@kosmos_api_auth
@require_GET
def api_matters(request):
    """The matters the token's user may see, by name. ``?q=`` narrows by
    name, client or client reference; ``?status=`` (repeatable) by status."""
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
    return JsonResponse(
        {
            "matters": [
                matter_fields(matter, request)
                for matter in matters.order_by("name", "id")
            ]
        }
    )


@kosmos_api_auth
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
