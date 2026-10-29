"""Linking a matter to its folder, and the Files status page.

The link is a person's decision: the modal lists every free folder under
the matter roots, floats the best name match to the top as a suggestion,
and stores nothing until a folder is clicked and saved. The status page
is the operator's view of the watcher.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.html import format_html
from django.views.decorators.http import require_POST

from apps.accounts.access import matter_access_required
from apps.matters.models import Matter

from . import tree
from .models import FilesState, MatterFolder, PdfFile
from .watcher import refresh_links

HEARTBEAT_STALE_SECONDS = 120


def _matter_name_for(user, matter):
    """The matter's name when the user may see it, else None (another
    matter holds a folder; which one is not for a user who is not on it)."""
    if matter is not None and user.has_matter_access(matter):
        return str(matter)
    return None


def _current(matter):
    return MatterFolder.objects.filter(matter=matter).first()


@login_required
@matter_access_required
def folder_link_modal(request, matter_id):
    matter = get_object_or_404(Matter, pk=matter_id)
    current = _current(matter)
    taken = {
        folder.path: folder.matter
        for folder in MatterFolder.objects.exclude(matter=matter).select_related(
            "matter"
        )
    }
    paths = tree.list_matter_folders()
    free = [path for path in paths if path not in taken]
    suggested = tree.suggest(matter.name or "", free)
    rows = [
        {
            "path": path,
            "name": tree.folder_name(path),
            "root": path.split("/", 1)[0],
            "taken": path in taken,
            "taken_by": _matter_name_for(request.user, taken.get(path)),
            "suggested": path == suggested,
            "current": current is not None and path == current.path,
        }
        for path in paths
    ]
    rows.sort(key=lambda row: (not row["suggested"], row["path"].lower()))
    context = {
        "matter": matter,
        "configured": tree.configured(),
        "current": current,
        "rows": rows,
        "suggested": suggested,
        "roots_text": ", ".join(tree.matter_roots()),
    }
    return render(request, "drive/folder-link-modal.html", context)


@login_required
@matter_access_required
@require_POST
def folder_link(request, matter_id):
    matter = get_object_or_404(Matter, pk=matter_id)
    path = (request.POST.get("path") or "").strip().strip("/")
    # 200 on a refusal so HTMX swaps the message into the modal's error slot.
    if not path:
        return HttpResponse('<p class="error-text">Choose a folder to link first.</p>')
    if path not in tree.list_matter_folders():
        return HttpResponse(
            '<p class="error-text">That folder is not under a matter root any '
            "more. Close and reopen this dialog.</p>"
        )
    clash = MatterFolder.objects.filter(path=path).exclude(matter=matter).first()
    if clash:
        return HttpResponse(
            format_html(
                '<p class="error-text">“{}” is already linked to {}. '
                "Unlink it there first.</p>",
                tree.folder_name(path),
                _matter_name_for(request.user, clash.matter) or "another matter",
            )
        )
    MatterFolder.objects.update_or_create(
        matter=matter,
        defaults={
            "path": path,
            "linked_by": request.user,
            "linked_at": timezone.now(),
            "missing_since": None,
        },
    )
    refresh_links()
    return HttpResponse(status=204, headers={"HX-Refresh": "true"})


@login_required
@matter_access_required
@require_POST
def folder_unlink(request, matter_id):
    matter = get_object_or_404(Matter, pk=matter_id)
    MatterFolder.objects.filter(matter=matter).delete()
    refresh_links()
    return HttpResponse(status=204, headers={"HX-Refresh": "true"})


@login_required
def files_status(request):
    """Settings > Files: the tree, the watcher, and what it found."""
    if not request.user.is_admin:
        raise PermissionDenied
    state = FilesState.get()
    now = timezone.now()
    heartbeat_age = (
        (now - state.watcher_seen_at).total_seconds() if state.watcher_seen_at else None
    )
    counts = PdfFile.objects.aggregate(
        total=Count("id"),
        without_text=Count("id", filter=Q(has_text=False)),
        ocr_done=Count("id", filter=Q(ocr_status="done")),
        failed=Count("id", filter=Q(ocr_status="failed") & ~Q(size=0)),
        pending=Count("id", filter=Q(ocr_status="pending")),
    )
    context = {
        "app": "settings",
        "subapp": "integrations",
        "configured": tree.configured(),
        "root": tree.root(),
        "roots_text": ", ".join(tree.matter_roots()),
        "state": state,
        "watcher_alive": heartbeat_age is not None
        and heartbeat_age < HEARTBEAT_STALE_SECONDS,
        "counts": counts,
        # Empty files are listed under "Empty files", not as OCR failures.
        "failures": PdfFile.objects.filter(ocr_status="failed")
        .exclude(size=0)
        .order_by("path")[:50],
        "linked": MatterFolder.objects.select_related("matter").order_by("path"),
        "missing": MatterFolder.objects.filter(missing_since__isnull=False)
        .select_related("matter")
        .order_by("path"),
        "unclaimed": state.unclaimed_folders,
    }
    return render(request, "drive/status.html", context)
