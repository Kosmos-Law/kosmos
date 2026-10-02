from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.case.courtlistener import (
    fetch_cluster,
    format_citations_with_year,
    lookup_citation,
)
from apps.case.models import CaseLaw
from apps.case.views import get_matter_from_url, set_last_tab

from .courtlistener import count_forward_citations
from .jurisdictions import STATES
from .models import CaseBrief, CitationVerification, ResearchQuery, ResearchResult
from .tasks import (
    ASSESS_INTERRUPTED,
    _rank_candidates,
    assessment_lost,
    generate_brief,
    generate_caselaw_summary,
    process_brief_phase,
    process_research_query,
    reap_stale_briefs,
    reap_stale_queries,
    reap_stale_result,
    refine_research_query,
    review_more_citations,
    review_result,
    sanitize_query,
    start_citation_assessment,
    start_review,
    start_single_brief,
)


def _active_query(request, matter):
    """The user's latest query on the matter, for the Search sub-tab: a run
    still in progress picks up where it was. Stranded runs are flagged
    first, so what is shown is never a spinner that cannot end."""
    reap_stale_queries(matter, request.user)
    return (
        ResearchQuery.objects.filter(matter=matter, created_by=request.user)
        # Validating a typed citation files its case under a placeholder
        # query (complete, never searched). It is not a search to resume
        # and would show here as an empty "No results found" run.
        .exclude(status="complete", structured_query="")
        .order_by("-created_at")
        .first()
    )


def get_research_data(request, matter, matter_id):
    """Get research data for the case tab.

    Every way into the Research tab (the full page, the tab switch and the
    list refresh) renders the Search sub-tab from this, so each of them
    shows the run in progress."""
    return {
        "states": STATES,
        "active_query": _active_query(request, matter) if matter else None,
    }


def _user_briefs(matter, user):
    return CaseBrief.objects.filter(matter=matter, created_by=user)


def _mark_saved_state(results, matter, user):
    """Note on each result what the user has already saved from it: the
    bookmark (a saved case on the matter) and the user's own brief.

    Briefs are per user (each is written against its author's own research
    question), so only the user's own count as saved."""
    cluster_ids = [r.cluster_id for r in results if r.cluster_id]
    briefs = {}
    bookmarked = set()
    if cluster_ids:
        # Newest first (the model's ordering), so a case keeps its newest.
        for brief in _user_briefs(matter, user).filter(cluster_id__in=cluster_ids):
            briefs.setdefault(brief.cluster_id, brief)
        bookmarked = set(
            CaseLaw.objects.filter(
                matter=matter, cluster_id__in=cluster_ids
            ).values_list("cluster_id", flat=True)
        )
    for r in results:
        r.existing_brief = briefs.get(r.cluster_id) if r.cluster_id else None
        r.brief_generating = bool(
            r.existing_brief and r.existing_brief.status in ("pending", "generating")
        )
        r.is_bookmarked = bool(r.cluster_id) and r.cluster_id in bookmarked


def _render_result_row(request, result, **extra):
    """One result card. Every re-render of a card (a poll, a save, a brief)
    comes through here so each carries the same saved state as the list."""
    matter = result.query.matter
    _mark_saved_state([result], matter, request.user)
    return render(
        request,
        "case/research/result-row.html",
        {"result": result, "matter": matter, **extra},
    )


@login_required
def research_index(request, matter_id):
    """Main research view (full page load)."""
    matter, matters = get_matter_from_url(request, matter_id)
    set_last_tab(request, matter_id, "research")

    context = {
        "app": "matters",
        "subapp": "research",
        "matter": matter,
        "matters": matters,
        "research_tab": "search",
    } | get_research_data(request, matter, matter_id)

    return render(request, "case/research/main.html", context)


@login_required
def research_list(request, matter_id):
    """HTMX partial for research tab content."""
    matter, _ = get_matter_from_url(request, matter_id)

    context = {
        "matter": matter,
        "research_tab": "search",
    } | get_research_data(request, matter, matter_id)

    return render(request, "case/research/list.html", context)


# ── Internal sub-tab views ────────────────────────────────────────────────


@login_required
def research_caselaws_tab(request, matter_id):
    """HTMX partial for the Case Law sub-tab content."""
    from apps.case.caselaws.views import get_caselaws_data

    matter, _ = get_matter_from_url(request, matter_id)

    context = {
        "matter": matter,
        "research_tab": "caselaws",
    } | get_caselaws_data(request, matter, matter_id)

    return render(request, "case/research/list.html", context)


@login_required
def research_search_tab(request, matter_id):
    """HTMX partial for the Search sub-tab content."""
    matter, _ = get_matter_from_url(request, matter_id)

    context = {
        "matter": matter,
        "research_tab": "search",
    } | get_research_data(request, matter, matter_id)

    return render(request, "case/research/list.html", context)


@login_required
def research_history_tab(request, matter_id):
    """HTMX partial for the History sub-tab content."""
    matter, _ = get_matter_from_url(request, matter_id)

    queries = ResearchQuery.objects.filter(matter=matter, created_by=request.user)[:50]

    context = {
        "matter": matter,
        "research_tab": "history",
        "queries": queries,
    }

    return render(request, "case/research/list.html", context)


@login_required
def research_review_tab(request, matter_id):
    """HTMX partial for the Review sub-tab content."""
    matter, _ = get_matter_from_url(request, matter_id)

    result_id = request.GET.get("result")
    context = {
        "matter": matter,
        "research_tab": "review",
    }

    if result_id:
        result = get_object_or_404(
            ResearchResult,
            pk=result_id,
            query__matter=matter,
            query__created_by=request.user,
        )
        context["result"] = reap_stale_result(result)
    else:
        reviewed_results = ResearchResult.objects.filter(
            query__matter=matter,
            query__created_by=request.user,
            verify_status="complete",
        ).select_related("query")
        context["reviewed_results"] = reviewed_results

    return render(request, "case/research/list.html", context)


# ── Search flow ───────────────────────────────────────────────────────────


@login_required
def research_search(request, matter_id):
    """POST: create a new research query."""
    if request.method != "POST":
        return HttpResponse(status=405)

    matter, _ = get_matter_from_url(request, matter_id)

    query_text = request.POST.get("query_text", "").strip()
    state = request.POST.get("state", "")
    include_federal = request.POST.get("include_federal") == "on"

    if not query_text:
        return HttpResponse(
            '<div class="research-error">Please enter a search query.</div>'
        )

    # Auto-expire queries older than 30 days
    from datetime import timedelta

    from django.utils import timezone

    threshold = timezone.now() - timedelta(days=30)
    ResearchQuery.objects.filter(
        matter=matter, created_by=request.user, created_at__lt=threshold
    ).delete()

    query = ResearchQuery.objects.create(
        matter=matter,
        query_text=query_text,
        state=state,
        include_federal=include_federal,
        status="pending",
        created_by=request.user,
    )

    refine_research_query(query.id)

    return render(
        request,
        "case/research/refinement.html",
        {"query": query, "matter": matter},
    )


@login_required
def research_results(request, matter_id, query_id):
    """View results for a specific query with sorting and pagination."""
    from apps.management.pagination import CustomPaginator

    matter, _ = get_matter_from_url(request, matter_id)

    reap_stale_queries(matter, request.user)

    query = get_object_or_404(
        ResearchQuery, pk=query_id, matter=matter, created_by=request.user
    )

    sort = request.GET.get("sort", "relevance")
    sort_map = {
        "relevance": "position",
        "date": "-date_filed",
        "citations": "-forward_citation_count",
    }
    order_field = sort_map.get(sort, "-score")
    # Ruled-out rows (triage rejects and low-verdict briefs) are kept for
    # inspection but live in their own collapsed section, unpaginated.
    ruled_out = list(
        query.results.filter(relevance__in=["rejected", "low"]).order_by("position")
    )
    results = query.results.exclude(relevance__in=["rejected", "low"]).order_by(
        order_field
    )

    # At the selection gate, the results area shows the ranked candidate
    # list (with the pre-read signals) instead of result cards.
    recommended_candidates = []
    other_candidates = []
    if query.status == "selecting":
        pending = list(query.results.filter(relevance="pending").order_by("position"))
        ordered, _ = _rank_candidates(pending)
        recommended_candidates = [r for r in ordered if r.recommended]
        other_candidates = [r for r in ordered if not r.recommended]

    session_key = f"research_results_{query_id}"
    pagination = CustomPaginator(
        results, per_page=5, request=request, session_key=session_key
    )
    results = pagination.get_object_list()

    results = list(results)
    _mark_saved_state(results, matter, request.user)

    return render(
        request,
        "case/research/results.html",
        {
            "query": query,
            "results": results,
            "ruled_out": ruled_out,
            "recommended_candidates": recommended_candidates,
            "other_candidates": other_candidates,
            "matter": matter,
            "sort": sort,
            "pagination": pagination,
            "session_key": session_key,
            "trigger_key": "researchResultsChanged",
        },
    )


@login_required
def research_detail(request, matter_id, query_id):
    """View a specific query with search form and results."""
    matter, matters = get_matter_from_url(request, matter_id)
    set_last_tab(request, matter_id, "research")
    query = get_object_or_404(
        ResearchQuery, pk=query_id, matter=matter, created_by=request.user
    )
    results = query.results.all()
    return render(
        request,
        "case/research/main.html",
        {
            "app": "matters",
            "subapp": "research",
            "matter": matter,
            "matters": matters,
            "research_tab": "search",
            "states": STATES,
            "active_query": query,
            "results": results,
        },
    )


@login_required
def research_confirm(request, matter_id, query_id):
    """POST: confirm structured query and start search."""
    if request.method != "POST":
        return HttpResponse(status=405)

    matter, _ = get_matter_from_url(request, matter_id)
    query = get_object_or_404(
        ResearchQuery, pk=query_id, matter=matter, created_by=request.user
    )

    variants = list(query.query_variants or [])
    if variants:
        # The approval screen posts one checkbox + editable text per
        # proposed variant; the user runs any subset, edited freely.
        selected = []
        for i, variant in enumerate(variants):
            if f"use_{i}" not in request.POST:
                continue
            text = sanitize_query(request.POST.get(f"q_{i}", "").strip()[:300])
            if text:
                selected.append(
                    {"label": variant.get("label", "Search"), "query": text}
                )
        if not selected:
            return render(
                request,
                "case/research/refinement.html",
                {
                    "query": query,
                    "matter": matter,
                    "error": "Select at least one search to run.",
                },
            )
        query.query_variants = selected
        query.structured_query = "\n".join(v["query"] for v in selected)
        query.save(update_fields=["query_variants", "structured_query"])
    else:
        structured_query = request.POST.get("structured_query", "").strip()
        if structured_query:
            query.structured_query = sanitize_query(structured_query)
            query.save(update_fields=["structured_query"])

    query.status = "searching"
    query.save(update_fields=["status"])

    process_research_query(query.id)

    context = {"query": query, "results": query.results.all(), "matter": matter}
    return render(request, "case/research/refinement.html", context)


@login_required
def research_select_cases(request, matter_id, query_id):
    """POST: run full-opinion briefs on the user-selected cases.

    The second gate: reads are the expensive stage, so after search +
    triage the user picks which cases get pulled (the pipeline's
    recommendation arrives prechecked). Ruled-out rows may be selected
    too - a wrong triage call is overridable by hand.
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    matter, _ = get_matter_from_url(request, matter_id)
    query = get_object_or_404(
        ResearchQuery, pk=query_id, matter=matter, created_by=request.user
    )

    selected_ids = [
        int(key[5:])
        for key in request.POST
        if key.startswith("case_") and key[5:].isdigit()
    ]
    valid_ids = set(
        query.results.filter(
            relevance__in=["pending", "rejected", "low", "none"]
        ).values_list("id", flat=True)
    )
    keep = [rid for rid in selected_ids if rid in valid_ids]

    if not keep:
        pending = list(query.results.filter(relevance="pending").order_by("position"))
        ordered, _ = _rank_candidates(pending)
        return render(
            request,
            "case/research/results.html",
            {
                "query": query,
                "matter": matter,
                "results": [],
                "ruled_out": list(
                    query.results.filter(relevance__in=["rejected", "low"]).order_by(
                        "position"
                    )
                ),
                "recommended_candidates": [r for r in ordered if r.recommended],
                "other_candidates": [r for r in ordered if not r.recommended],
                "selection_error": "Select at least one case to brief.",
                "sort": "relevance",
            },
        )

    # Unselected candidates step aside (still briefable later via the
    # per-card button); selections - resurrected ruled-out rows included -
    # join the briefing queue.
    query.results.filter(relevance="pending").exclude(pk__in=keep).update(
        relevance="none", status_message="Not selected"
    )
    query.results.filter(pk__in=keep).update(
        relevance="pending", status_message="Queued for briefing"
    )

    query.status = "processing"
    query.save(update_fields=["status"])

    process_brief_phase(query.id)

    return research_results(request, matter_id, query_id)


@login_required
def research_delete(request, matter_id, query_id):
    """POST: delete a research query."""
    if request.method != "POST":
        return HttpResponse(status=405)

    matter, _ = get_matter_from_url(request, matter_id)
    query = get_object_or_404(
        ResearchQuery, pk=query_id, matter=matter, created_by=request.user
    )
    query.delete()

    if request.headers.get("HX-Target") == "research":
        queries = ResearchQuery.objects.filter(matter=matter, created_by=request.user)[
            :50
        ]
        return render(
            request,
            "case/research/list.html",
            {"matter": matter, "research_tab": "history", "queries": queries},
        )

    response = HttpResponse(status=200)
    response["HX-Redirect"] = reverse("case:research-index", args=[matter_id])
    return response


# ── Polling endpoints (object-specific, no matter_id needed) ──────────────


@login_required
def query_status(request, query_id):
    """Poll for query processing status — used by refinement polling."""
    query = get_object_or_404(ResearchQuery, pk=query_id, created_by=request.user)
    # A refinement whose task was lost would otherwise keep this poll alive.
    reap_stale_queries(query.matter, request.user)
    query.refresh_from_db()
    return render(
        request,
        "case/research/refinement.html",
        {"query": query, "matter": query.matter},
    )


@login_required
def result_status(request, result_id):
    """Poll for individual result status."""
    result = get_object_or_404(
        ResearchResult, pk=result_id, query__created_by=request.user
    )
    return _render_result_row(request, reap_stale_result(result))


# ── Review flow (object-specific) ────────────────────────────────────────


@login_required
def research_review(request, result_id):
    """POST: start review from a search result."""
    if request.method != "POST":
        return HttpResponse(status=405)

    result = get_object_or_404(
        ResearchResult, pk=result_id, query__created_by=request.user
    )
    matter = result.query.matter

    result = reap_stale_result(result)
    start_review(result.id, review_result)
    result.refresh_from_db()

    context = {
        "matter": matter,
        "research_tab": "review",
        "result": result,
    }
    return render(request, "case/research/list.html", context)


@login_required
def research_review_lookup(request, matter_id):
    """POST: look up a citation and start review."""
    if request.method != "POST":
        return HttpResponse(status=405)

    matter, _ = get_matter_from_url(request, matter_id)

    citation_text = request.POST.get("citation", "").strip()
    if not citation_text:
        context = {
            "matter": matter,
            "research_tab": "review",
        }
        return render(request, "case/research/list.html", context)

    lookup = lookup_citation(citation_text)
    if not lookup.found:
        context = {
            "matter": matter,
            "research_tab": "review",
            "lookup_error": lookup.error or "Citation not found.",
            "lookup_citation": citation_text,
        }
        return render(request, "case/research/list.html", context)

    fwd_count = None
    cluster = fetch_cluster(lookup.cluster_id)
    if cluster:
        sub_opinions = cluster.get("sub_opinions", [])
        if sub_opinions:
            try:
                opinion_id = int(sub_opinions[0].rstrip("/").split("/")[-1])
                fwd_count = count_forward_citations(opinion_id)
            except (ValueError, IndexError):
                pass

    citation_str = lookup.citation
    if lookup.date_filed:
        citation_str = f"{citation_str} ({lookup.date_filed.year})"

    query = ResearchQuery.objects.create(
        matter=matter,
        query_text=citation_text,
        status="complete",
        created_by=request.user,
    )

    result = ResearchResult.objects.create(
        query=query,
        position=1,
        case_name=lookup.case_name,
        citation=citation_str,
        court=lookup.court,
        date_filed=str(lookup.date_filed) if lookup.date_filed else "",
        cluster_id=lookup.cluster_id,
        courtlistener_url=(
            f"https://www.courtlistener.com{lookup.absolute_url}"
            if lookup.absolute_url
            else ""
        ),
        forward_citation_count=fwd_count,
        relevance="high",
        verify_status="verifying",
    )

    review_result(result.id)

    # Rendered into the tab like every other Validate, so the page keeps
    # its frame and the status poll runs.
    context = {
        "matter": matter,
        "research_tab": "review",
        "result": result,
    }
    return render(request, "case/research/list.html", context)


@login_required
def research_review_status(request, result_id):
    """Poll for review status."""
    result = get_object_or_404(
        ResearchResult, pk=result_id, query__created_by=request.user
    )
    result = reap_stale_result(result)
    return render(
        request,
        "case/research/review-content.html",
        {"result": result, "matter": result.query.matter},
    )


@login_required
def research_review_more(request, result_id):
    """POST: evaluate more unevaluated forward citations."""
    if request.method != "POST":
        return HttpResponse(status=405)

    result = get_object_or_404(
        ResearchResult, pk=result_id, query__created_by=request.user
    )

    result = reap_stale_result(result)
    start_review(result.id, review_more_citations)
    result.refresh_from_db()

    return render(
        request,
        "case/research/review-content.html",
        {"result": result, "matter": result.query.matter},
    )


@login_required
def research_assess_citation(request, verification_id):
    """POST: assess a single forward citation."""
    if request.method != "POST":
        return HttpResponse(status=405)

    verification = get_object_or_404(
        CitationVerification,
        pk=verification_id,
        result__query__created_by=request.user,
    )

    start_citation_assessment(verification)

    return render(
        request,
        "case/research/citation-item.html",
        {"v": verification, "assessing": True},
    )


@login_required
def research_citation_status(request, verification_id):
    """Poll for a single citation assessment status."""
    verification = get_object_or_404(
        CitationVerification,
        pk=verification_id,
        result__query__created_by=request.user,
    )
    # A lost task never writes an outcome: past the stale window the row
    # stops polling, says so, and offers Assess again.
    lost = assessment_lost(verification)
    return render(
        request,
        "case/research/citation-item.html",
        {
            "v": verification,
            "assessing": not verification.summary and not lost,
            "assess_error": ASSESS_INTERRUPTED if lost else "",
        },
    )


# ── Save to Case Law ─────────────────────────────────────────────────────


@login_required
def research_save_to_caselaws(request, result_id):
    """POST: save a research result to the matter's case law library."""
    if request.method != "POST":
        return HttpResponse(status=405)

    result = get_object_or_404(
        ResearchResult, pk=result_id, query__created_by=request.user
    )
    matter = result.query.matter

    # Check for duplicate
    if result.cluster_id:
        existing = CaseLaw.objects.filter(
            matter=matter, cluster_id=result.cluster_id
        ).first()
        if existing:
            return _render_result_row(request, result)

    # Build the CaseLaw row from the cluster the result already points at.
    # The old path round-tripped through the citation-lookup API, which
    # cannot resolve a slip opinion (no reporter citation to parse).
    cluster = fetch_cluster(result.cluster_id) if result.cluster_id else {}
    if not cluster:
        return _render_result_row(
            request, result, save_error="Could not fetch case data from CourtListener."
        )

    date_filed = None
    if cluster.get("date_filed"):
        from datetime import date

        try:
            date_filed = date.fromisoformat(cluster["date_filed"])
        except ValueError:
            date_filed = None

    # The cluster's "court" field is an API URL; the display name comes
    # from the search result and the id from the URL tail.
    court_id = str(cluster.get("court") or "").rstrip("/").split("/")[-1]

    opinion_id = None
    sub_opinions = cluster.get("sub_opinions", [])
    if sub_opinions:
        try:
            opinion_id = int(sub_opinions[0].rstrip("/").split("/")[-1])
        except (ValueError, IndexError):
            opinion_id = None

    citation = (
        format_citations_with_year(cluster.get("citations", []), None)
        or result.citation
    )

    case_law = CaseLaw.objects.create(
        matter=matter,
        case_name=cluster.get("case_name") or result.case_name,
        citation=citation,
        court=result.court,
        court_id=court_id,
        date_filed=date_filed,
        docket_number=str(cluster.get("docket_number") or ""),
        cluster_id=result.cluster_id,
        opinion_id=opinion_id,
        courtlistener_url=result.courtlistener_url
        or (
            f"https://www.courtlistener.com{cluster['absolute_url']}"
            if cluster.get("absolute_url")
            else ""
        ),
        created_by=request.user,
        updated_by=request.user,
    )

    generate_caselaw_summary(case_law.id)

    return _render_result_row(request, result)


# ── Abstracts (Case Briefs) ──────────────────────────────────────────────


@login_required
def research_abstracts_tab(request, matter_id):
    """HTMX partial for the Abstracts sub-tab content."""
    matter, _ = get_matter_from_url(request, matter_id)

    briefs = _user_briefs(matter, request.user)
    reap_stale_briefs(briefs)

    context = {
        "matter": matter,
        "research_tab": "abstracts",
        "briefs": briefs,
    }

    return render(request, "case/research/list.html", context)


@login_required
def research_brief_detail(request, brief_id):
    """HTMX partial for viewing a single case brief."""
    reap_stale_briefs(CaseBrief.objects.filter(pk=brief_id, created_by=request.user))
    brief = get_object_or_404(CaseBrief, pk=brief_id, created_by=request.user)
    return render(
        request,
        "case/research/brief-detail.html",
        {"brief": brief, "matter": brief.matter},
    )


@login_required
def research_save_brief(request, result_id):
    """POST: generate a case brief from a research result."""
    if request.method != "POST":
        return HttpResponse(status=405)

    result = get_object_or_404(
        ResearchResult, pk=result_id, query__created_by=request.user
    )
    matter = result.query.matter

    # One brief per case per user: a colleague's brief of the same case
    # answers a different question and is not this user's to open.
    if result.cluster_id:
        existing = (
            _user_briefs(matter, request.user)
            .filter(cluster_id=result.cluster_id)
            .exists()
        )
        if existing:
            return _render_result_row(request, result)

    brief = CaseBrief.objects.create(
        matter=matter,
        result=result,
        case_name=result.case_name,
        citation=result.citation,
        court=result.court,
        date_filed=result.date_filed,
        cluster_id=result.cluster_id,
        query_text=result.query.query_text,
        created_by=request.user,
        updated_by=request.user,
    )

    generate_brief(brief.id)

    return _render_result_row(request, result)


@login_required
def research_brief_status(request, brief_id):
    """Poll for brief generation status."""
    reap_stale_briefs(CaseBrief.objects.filter(pk=brief_id, created_by=request.user))
    brief = get_object_or_404(CaseBrief, pk=brief_id, created_by=request.user)
    return render(
        request,
        "case/research/brief-status.html",
        {"brief": brief},
    )


@login_required
def research_delete_brief(request, brief_id):
    """POST: delete a case brief."""
    if request.method != "POST":
        return HttpResponse(status=405)

    brief = get_object_or_404(CaseBrief, pk=brief_id, created_by=request.user)
    matter = brief.matter
    brief.delete()

    briefs = _user_briefs(matter, request.user)
    return render(
        request,
        "case/research/list.html",
        {"matter": matter, "research_tab": "abstracts", "briefs": briefs},
    )


@login_required
def research_summarize_result(request, result_id):
    """POST: request AI summarization of a single result."""
    if request.method != "POST":
        return HttpResponse(status=405)

    result = get_object_or_404(
        ResearchResult, pk=result_id, query__created_by=request.user
    )

    reap_stale_result(result)
    start_single_brief(result_id)

    # Re-fetch: the card now shows the job (pending) and polls for it.
    result.refresh_from_db()
    return _render_result_row(request, result)
