from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.access import filter_matters_for_user, matter_access_required

# Re-exported: the case tab view modules import get_session_key from here.
from apps.management.selection import get_session_key  # noqa: F401
from apps.matters.models import Matter

# Valid tabs for the case app (get_last_tab sanitizes stale session
# values against this list)
VALID_TABS = [
    "documents",
    "highlights",
    "facts",
    "witnesses",
    "notes",
    "emails",
    "labels",
    "search",
    "ai",
    "caselaws",
]
DEFAULT_TAB = "documents"


def get_tab_session_key(matter_id):
    """Get the session key for storing the active tab for a matter."""
    return f"case_tab_{matter_id}"


def get_last_tab(request, matter_id):
    """Get the last active tab for a matter, or default to documents. A
    remembered tab whose integration has since gone (AI, CourtListener)
    falls back too."""
    tab = request.session.get(get_tab_session_key(matter_id), DEFAULT_TAB)
    if tab not in VALID_TABS or not tab_available(request.user, tab, matter_id):
        return DEFAULT_TAB
    return tab


def tab_available(user, tab, matter_id=None):
    """Whether this server and user can show ``tab`` at all."""
    if tab == "ai":
        from apps.settings.ai import ai_enabled

        return ai_enabled()
    if tab == "caselaws":
        from apps.case.courtlistener import caselaw_available

        return caselaw_available(user)
    if tab == "emails" and matter_id is not None:
        # Hidden on a server without Google sign-in unless the matter
        # already holds synced emails.
        from apps.mail.google import emails_tab_available

        return emails_tab_available(matter_id)
    return True


def set_last_tab(request, matter_id, tab):
    """Save the active tab for a matter."""
    if tab in VALID_TABS:
        request.session[get_tab_session_key(matter_id)] = tab


def redirect_to_tab(matter_id, tab):
    """Redirect to the appropriate index view for the given tab."""
    return redirect(f"case:{tab}-index", matter_id=matter_id)


@login_required
def case_index(request):
    """Redirect to the last viewed matter, or the first open matter."""
    # Check for last viewed matter in session
    last_matter_id = request.session.get("last_viewed_matter")

    if last_matter_id:
        # Verify the matter still exists and is open
        matter = Matter.objects.filter(id=last_matter_id, status="Open").first()
        if matter and request.user.has_matter_access(matter):
            tab = get_last_tab(request, matter.id)
            return redirect_to_tab(matter.id, tab)

    # Fall back to first open matter (filtered by access)
    matters = filter_matters_for_user(
        Matter.objects.filter(status="Open").order_by("name"), request.user
    )
    matter = matters.first()
    if matter:
        request.session["last_viewed_matter"] = matter.id
        tab = get_last_tab(request, matter.id)
        return redirect_to_tab(matter.id, tab)

    # No open matters - show empty state
    return redirect("case:no-matter")


@login_required
def no_matter(request):
    """Show when no matters are available."""
    return render(request, "case/no-matter.html")


@login_required
@matter_access_required
def select_matter(request, matter_id):
    """Change the selected matter and redirect to last used tab."""
    matter = get_object_or_404(Matter, pk=matter_id)

    # Store as last viewed matter
    request.session["last_viewed_matter"] = matter.id

    # Redirect to the last used tab for this matter
    tab = get_last_tab(request, matter.id)
    return redirect_to_tab(matter.id, tab)


@login_required
@matter_access_required
def mode_content(request, matter_id):
    """Return case mode content partial for HTMX, or redirect for regular request."""
    matter = get_object_or_404(Matter, pk=matter_id)
    tab = get_last_tab(request, matter_id)

    # Store as last viewed matter
    request.session["last_viewed_matter"] = matter.id

    if not request.headers.get("HX-Request"):
        return redirect_to_tab(matter_id, tab)

    matters = filter_matters_for_user(
        Matter.objects.filter(status="Open").order_by("name"), request.user
    )

    context = {
        "matter": matter,
        "matters": matters,
        "mode": "case",
        "subapp": tab,
    }

    # Fetch tab data directly for single-request loading
    tab_data = _get_case_tab_data(request, matter, matters, matter_id, tab)
    context.update(tab_data)

    return render(request, "case/includes/case-content.html", context)


@login_required
@matter_access_required
def tab_content(request, matter_id, tab):
    """Return tab content with wrapper for HTMX tab switching."""
    matter = get_object_or_404(Matter, pk=matter_id)
    matters = filter_matters_for_user(
        Matter.objects.filter(status="Open").order_by("name"), request.user
    )

    # Update last viewed tab
    set_last_tab(request, matter_id, tab)

    context = {
        "matter": matter,
        "matters": matters,
        "subapp": tab,
    }

    tab_data = _get_case_tab_data(request, matter, matters, matter_id, tab)
    context.update(tab_data)

    return render(request, "case/includes/case-tab-content.html", context)


def _get_case_tab_data(request, matter, matters, matter_id, tab):
    """Fetch data for the specified case tab."""
    from apps.case.documents.views import get_document_data
    from apps.case.facts.views import get_facts_data
    from apps.case.highlights.views import get_highlights_data
    from apps.case.labels.views import get_label_data
    from apps.case.notes.views import get_notes_data
    from apps.case.search.views import get_search_data
    from apps.case.witnesses.views import get_witnesses_data

    if tab == "documents":
        return {
            "tab_template": "case/documents/list.html",
            **get_document_data(request, matter_id),
        }

    elif tab == "highlights":
        return {
            "tab_template": "case/highlights/list.html",
            **get_highlights_data(request, matter, matter_id),
        }

    elif tab == "facts":
        return {
            "tab_template": "case/facts/list.html",
            **get_facts_data(request, matter, matter_id),
        }

    elif tab == "witnesses":
        return {
            "tab_template": "case/witnesses/list.html",
            **get_witnesses_data(request, matter, matter_id),
        }

    elif tab == "notes":
        return {
            "tab_template": "case/notes/list.html",
            **get_notes_data(request, matter, matter_id),
        }

    elif tab == "emails":
        from apps.mail.views import get_emails_data

        return {
            "tab_template": "case/emails/list.html",
            **get_emails_data(request, matter, matter_id),
        }

    elif tab == "labels":
        return {
            "tab_template": "case/labels/list.html",
            **get_label_data(request, matter_id),
        }

    elif tab == "search":
        return {
            "tab_template": "case/search/list.html",
            **get_search_data(request, matter, matter_id),
        }

    elif tab == "ai":
        from apps.case.ai.views import get_conversation_list_context

        return {
            "tab_template": "case/ai/list.html",
            **get_conversation_list_context(request, matter),
        }

    elif tab == "caselaws":
        from apps.case.caselaws.views import get_caselaws_data

        return {
            "tab_template": "case/caselaws/list.html",
            **get_caselaws_data(request, matter, matter_id),
        }

    # Fallback
    return {
        "tab_template": "case/documents/list.html",
        **get_document_data(request, matter_id),
    }


def get_matter_from_url(request, matter_id):
    """
    Get matter from URL parameter and update last_viewed_matter in session.
    Returns (matter, matters) tuple where matters is queryset of all open matters.
    """
    matters = filter_matters_for_user(
        Matter.objects.filter(status="Open").order_by("name"), request.user
    )
    matter = get_object_or_404(Matter, pk=matter_id)

    # Update last viewed matter in session
    request.session["last_viewed_matter"] = matter.id

    return matter, matters
