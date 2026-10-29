"""Template tags that let the core's pages show the matter's folder without
the core importing this app (the boundary in pyproject's import-linter
contracts is about Python imports; a template tag is loaded by name)."""

from django import template

from apps.drive import tree
from apps.drive.models import FilesState, MatterFolder

register = template.Library()


@register.inclusion_tag("drive/folder-row.html")
def matter_folder_row(matter):
    """The Overview table's Files row: the linked folder, or the link button.
    Renders nothing when the Files integration is off."""
    configured = tree.configured()
    folder = MatterFolder.objects.filter(matter=matter).first() if configured else None
    return {"matter": matter, "configured": configured, "folder": folder}


@register.inclusion_tag("drive/integration-card.html")
def files_integration_card():
    """Settings > Integrations: one line on the synced tree and a link to
    the status page."""
    configured = tree.configured()
    state = FilesState.get() if configured else None
    return {
        "configured": configured,
        "root": tree.root(),
        "state": state,
        "linked_count": MatterFolder.objects.count() if configured else 0,
        "unclaimed_count": len(state.unclaimed_folders) if state else 0,
    }
