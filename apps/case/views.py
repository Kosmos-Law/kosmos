from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.access import filter_matters_for_user, matter_access_required
from apps.case import tabs

# Re-exported: the case tab view modules import get_session_key from here.
from apps.management.selection import get_session_key  # noqa: F401
from apps.matters.models import Matter

DEFAULT_TAB = "documents"


def get_tab_session_key(matter_id):
    """Get the session key for storing the active tab for a matter."""
    return f"case_tab_{matter_id}"


def get_last_tab(request, matter_id):
    """Get the last active tab for a matter, or default to documents. A
    remembered tab whose integration has since gone (AI, CourtListener,
    Gmail) falls back too."""
    tab = request.session.get(get_tab_session_key(matter_id), DEFAULT_TAB)
    user = getattr(request, "user", None)
    if not tab_available(user, tab, matter_id):
        return DEFAULT_TAB
    return tab


def tab_available(user, tab, matter_id=None):
    """Whether this server and user can show ``tab`` at all (the registry
    in apps/case/tabs.py decides; an unknown name is not a tab)."""
    entry = tabs.get(tab)
    return entry is not None and entry.is_available(user, matter_id)


def set_last_tab(request, matter_id, tab):
    """Save the active tab for a matter."""
    if tabs.get(tab) is not None:
        request.session[get_tab_session_key(matter_id)] = tab


def redirect_to_tab(matter_id, tab):
    """Redirect to the appropriate index view for the given tab."""
    return redirect(tabs.get(tab).index_url, matter_id=matter_id)


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

    # The matter switcher passes the tab being viewed on the previous
    # matter; otherwise, or if this matter can't show it, the last used tab.
    tab = request.GET.get("tab")
    if not tab_available(request.user, tab, matter.id):
        tab = get_last_tab(request, matter.id)
    return redirect_to_tab(matter.id, tab)


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

    tab_data = _get_case_tab_data(request, matter, tab)
    context.update(tab_data)

    return render(request, "case/includes/case-tab-content.html", context)


def _get_case_tab_data(request, matter, tab):
    """The context of one tab: its registered data function's result, plus
    the tab itself and its template for the wrapper. An unknown tab renders
    Documents."""
    entry = tabs.get(tab) or tabs.get(DEFAULT_TAB)
    return {
        "tab": entry,
        "tab_template": entry.template,
        **entry.data(request, matter),
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
