from django.contrib.auth.decorators import login_required
from django.db.models import F, Func, Q, Value
from django.db.models.functions import Lower
from django.shortcuts import render
from watson import search as watson

from apps.accounts.access import filter_matters_for_user
from apps.contacts.models import Contact
from apps.intakes.models import Intake
from apps.matters.models import Matter
from apps.matters.proceedings.models import Proceeding
from apps.search import registry


class RegexpReplace(Func):
    """PostgreSQL REGEXP_REPLACE function for normalizing strings."""

    function = "REGEXP_REPLACE"


def normalize_case_number(text):
    """Remove non-alphanumeric characters and lowercase for fuzzy case number matching."""
    return "".join(c.lower() for c in text if c.isalnum())


def search_proceedings_by_case_number(search_text):
    """
    Search proceedings by case number with fuzzy matching.

    Normalizes both the search term and case numbers by removing
    non-alphanumeric characters, allowing matches like:
    - "2024cv12345" matches "2024-CV-12345"
    - "cv12345" matches "CV-12345"
    """
    normalized_search = normalize_case_number(search_text)
    if not normalized_search:
        return Proceeding.objects.none()

    # Annotate with normalized case_number (strip non-alphanumeric, lowercase)
    return (
        Proceeding.objects.annotate(
            normalized_case_number=Lower(
                RegexpReplace(
                    F("case_number"), Value("[^a-zA-Z0-9]"), Value(""), Value("g")
                )
            )
        )
        .filter(normalized_case_number__icontains=normalized_search)
        .select_related("matter")
    )


# The search's own scopes; the kinds other apps register (apps/search/
# registry.py) follow them.
BUILTIN_SCOPES = [
    ("matters", "Matters", Matter),
    ("proceedings", "Proceedings", Proceeding),
    ("contacts", "Contacts", Contact),
    ("intakes", "Intakes", Intake),
]


def search_scopes():
    return BUILTIN_SCOPES + [(k.key, k.label, k.model) for k in registry.kinds()]


# Synonym mappings for search
SEARCH_SYNONYMS = {
    "contract": ["agreement"],
    "agreement": ["contract"],
}


def expand_search_with_synonyms(query):
    """Expand a search query with synonyms, returning list of search terms."""
    terms = [query]
    query_lower = query.lower()
    for word, synonyms in SEARCH_SYNONYMS.items():
        if word in query_lower:
            for synonym in synonyms:
                terms.append(query.lower().replace(word, synonym))
    return terms


def scopes_for(user):
    """The search tabs a user gets: Intakes only with the Intakes permission."""
    scopes = search_scopes()
    if user.is_admin or user.perm_intakes:
        return scopes
    return [scope for scope in scopes if scope[0] != "intakes"]


@login_required
def index(request):
    active_scope = request.GET.get("scope") or request.session.get(
        "search_scope", "all"
    )
    context = {
        "app": "search",
        "action": "/search/results",
        "results": False,
        "scopes": scopes_for(request.user),
        "active_scope": active_scope,
    }
    return render(request, "search/content.html", context)


def _accessible_proceedings(text, accessible_matter_ids):
    """Proceedings whose case number matches, on matters the user can open."""
    return [
        proceeding
        for proceeding in search_proceedings_by_case_number(text)
        if proceeding.matter_id in accessible_matter_ids
    ]


@login_required
def results(request):
    text = request.POST.get("search_text", "").strip()

    # Get active scope from POST (tab selection)
    scope = request.POST.get("scope", "all")
    scope_matters = scope in ("all", "matters")
    scope_proceedings = scope in ("all", "proceedings")
    scope_contacts = scope in ("all", "contacts")
    # Intakes are searched only for those who may open them.
    scope_intakes = scope in ("all", "intakes") and (
        request.user.is_admin or request.user.perm_intakes
    )
    extra_kinds = [k for k in registry.kinds() if scope in ("all", k.key)]

    # Save to session for persistence
    request.session["search_scope"] = scope

    if not text:
        return render(
            request,
            "search/results.html",
            {
                "matters": None,
                "proceedings": None,
                "contacts": None,
                "intakes": None,
                "extra_sections": [],
                "has_results": False,
                "scopes": scopes_for(request.user),
                "active_scope": scope,
            },
        )

    matters = []
    proceedings = []
    contacts = []
    intakes = []
    extra = {kind.key: [] for kind in extra_kinds}

    # Matters, their proceedings and the registered kinds' rows surface only
    # for matters the user can open (each kind decides what that means).
    accessible_matter_ids = set(
        filter_matters_for_user(Matter.objects.all(), request.user).values_list(
            "id", flat=True
        )
    )

    # Digits only - use exact matching for IDs and phone numbers
    if text.isdigit():
        if scope_matters:
            matters = list(
                Matter.objects.filter(
                    client_reference_id=text, id__in=accessible_matter_ids
                ).order_by("name")
            )
        if scope_proceedings:
            proceedings = _accessible_proceedings(text, accessible_matter_ids)
        if scope_contacts:
            contacts = list(
                Contact.objects.filter(
                    Q(phone1__contains=text)
                    | Q(phone2__contains=text)
                    | Q(phone3__contains=text)
                ).order_by("name")
            )
        if scope_intakes:
            intakes = list(Intake.objects.filter(phone__contains=text).order_by("name"))
        # The registered kinds have no phone numbers; skipped for digits.
    else:
        # Expand search terms with synonyms
        search_terms = expand_search_with_synonyms(text)

        # Build list of models to search based on active scopes
        models_to_search = []
        if scope_matters:
            models_to_search.append(Matter)
        if scope_contacts:
            models_to_search.append(Contact)
        if scope_intakes:
            models_to_search.append(Intake)
        models_to_search.extend(kind.model for kind in extra_kinds)

        if models_to_search:
            # Use watson for fuzzy search
            seen_ids = {
                "matter": set(),
                "contact": set(),
                "intake": set(),
            }
            seen_extra = {kind.key: set() for kind in extra_kinds}

            for term in search_terms:
                search_results = watson.search(term, models=tuple(models_to_search))

                for result in search_results:
                    obj = result.object
                    if isinstance(obj, Matter) and obj.id not in seen_ids["matter"]:
                        seen_ids["matter"].add(obj.id)
                        if obj.id in accessible_matter_ids:
                            matters.append(obj)
                    elif isinstance(obj, Contact) and obj.id not in seen_ids["contact"]:
                        seen_ids["contact"].add(obj.id)
                        contacts.append(obj)
                    elif isinstance(obj, Intake) and obj.id not in seen_ids["intake"]:
                        seen_ids["intake"].add(obj.id)
                        intakes.append(obj)
                    else:
                        for kind in extra_kinds:
                            if (
                                isinstance(obj, kind.model)
                                and obj.id not in seen_extra[kind.key]
                            ):
                                seen_extra[kind.key].add(obj.id)
                                if kind.visible(
                                    obj, request.user, accessible_matter_ids
                                ):
                                    extra[kind.key].append(obj)
                                break

            # Search proceedings by case number (fuzzy match)
            if scope_proceedings:
                proceedings = _accessible_proceedings(text, accessible_matter_ids)

    context = {
        "app": "search",
        "action": "/search/results",
        "results": True,
        "matters": matters,
        "proceedings": proceedings,
        "contacts": contacts,
        "intakes": intakes,
        "extra_sections": [
            {"kind": kind, "rows": extra[kind.key]}
            for kind in extra_kinds
            if extra[kind.key]
        ],
        "scopes": scopes_for(request.user),
        "active_scope": scope,
    }
    context["has_results"] = any(
        (matters, proceedings, contacts, intakes, context["extra_sections"])
    )

    return render(request, "search/results.html", context)
