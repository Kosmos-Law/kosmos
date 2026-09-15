"""Token-authed JSON API over the practice-wide search (the same watson
index, synonym expansion, and case-number matching as the in-app search
page), for the Claude Desktop MCP server.

Results are manifest lines with handles for follow-up tools. Matters,
proceedings, and matter notes are limited to the user's accessible
matters (any status, since this is navigational); intakes require the
intakes permission.
"""

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from watson import search as watson

from apps.accounts.access import filter_matters_for_user
from apps.contacts.models import Contact
from apps.drafts.api_auth import kosmos_api_auth
from apps.intakes.models import Intake
from apps.matters.models import Matter
from apps.notes.models import Note
from apps.search.views import (
    SEARCH_SCOPES,
    expand_search_with_synonyms,
    search_proceedings_by_case_number,
)

SCOPE_NAMES = ("all",) + tuple(key for key, _label, _model in SEARCH_SCOPES)
RESULT_CAP = 20


def _matter_line(matter):
    line = f"- [matter:{matter.id}] {matter.name} ({matter.status}"
    if matter.client:
        line += f", client {matter.client.name}"
    line += ")"
    if matter.work_status:
        line += f"\n  Status note: {matter.work_status}"
    return line


def _proceeding_line(proceeding):
    bits = [proceeding.case_number or "no case number"]
    if proceeding.forum:
        bits.append(proceeding.forum)
    if proceeding.nickname:
        bits.append(proceeding.nickname)
    matter = proceeding.matter
    where = f" in [matter:{matter.id}] {matter.name}" if matter else ""
    return f"- [proceeding:{proceeding.id}] {', '.join(bits)}{where}"


def _contact_line(contact):
    bits = [b for b in (contact.company, contact.email, contact.phone1) if b]
    detail = f" ({', '.join(bits)})" if bits else ""
    return f"- [contact:{contact.id}] {contact.name}{detail}"


def _intake_line(intake):
    bits = [str(intake.date) if intake.date else None, intake.status]
    if intake.practice_area:
        bits.append(intake.practice_area.name)
    return f"- [intake:{intake.id}] {intake.name} ({', '.join(b for b in bits if b)})"


def _note_line(note):
    where = f" in [matter:{note.matter.id}] {note.matter.name}" if note.matter else ""
    return f"- [note:{note.id}] {note.title or 'Untitled'}{where}"


@kosmos_api_auth
@require_GET
def api_search(request):
    query = (request.GET.get("q") or "").strip()
    scope = request.GET.get("scope") or "all"
    if not query:
        return JsonResponse({"error": "Provide q."}, status=400)
    if scope not in SCOPE_NAMES:
        return JsonResponse(
            {"error": f"Unknown scope. Valid scopes: {', '.join(SCOPE_NAMES)}."},
            status=400,
        )
    user = request.api_user
    wanted = {key for key, _label, _model in SEARCH_SCOPES if scope in ("all", key)}
    if "intakes" in wanted and not (user.is_admin or user.perm_intakes):
        wanted.discard("intakes")

    accessible = filter_matters_for_user(Matter.objects.all(), user)
    accessible_ids = set(accessible.values_list("id", flat=True))
    found = {key: [] for key in wanted}

    if query.isdigit():
        if "matters" in wanted:
            found["matters"] = list(
                accessible.filter(client_reference_id=query).order_by("name")
            )
        if "contacts" in wanted:
            found["contacts"] = list(
                Contact.objects.filter(
                    Q(phone1__contains=query)
                    | Q(phone2__contains=query)
                    | Q(phone3__contains=query)
                ).order_by("name")
            )
        if "intakes" in wanted:
            found["intakes"] = list(
                Intake.objects.filter(phone__contains=query).order_by("name")
            )
    else:
        models = {
            "matters": Matter,
            "contacts": Contact,
            "intakes": Intake,
            "notes": Note,
        }
        to_search = tuple(models[key] for key in models if key in wanted)
        seen = set()
        for term in expand_search_with_synonyms(query):
            if not to_search:
                break
            for result in watson.search(term, models=to_search):
                obj = result.object
                if obj is None or (type(obj), obj.id) in seen:
                    continue
                seen.add((type(obj), obj.id))
                if isinstance(obj, Matter):
                    if obj.id in accessible_ids:
                        found["matters"].append(obj)
                elif isinstance(obj, Contact):
                    found["contacts"].append(obj)
                elif isinstance(obj, Intake):
                    found["intakes"].append(obj)
                elif isinstance(obj, Note):
                    if obj.matter_id is None or obj.matter_id in accessible_ids:
                        found["notes"].append(obj)
    if "proceedings" in wanted:
        found["proceedings"] = list(
            search_proceedings_by_case_number(query).filter(
                matter_id__in=accessible_ids
            )
        )

    formatters = {
        "matters": ("Matters", _matter_line),
        "proceedings": ("Proceedings", _proceeding_line),
        "contacts": ("Contacts", _contact_line),
        "intakes": ("Intakes", _intake_line),
        "notes": ("Notes", _note_line),
    }
    sections = []
    total = 0
    for key, _label, _model in SEARCH_SCOPES:
        rows = found.get(key) or []
        if not rows:
            continue
        title, fmt = formatters[key]
        total += len(rows)
        lines = [f"{title} ({len(rows)}):"] + [fmt(obj) for obj in rows[:RESULT_CAP]]
        if len(rows) > RESULT_CAP:
            lines.append(f"  ...and {len(rows) - RESULT_CAP} more; narrow the query.")
        sections.append("\n".join(lines))
    text = "\n\n".join(sections) or "No matches."
    return JsonResponse({"query": query, "scope": scope, "total": total, "text": text})
