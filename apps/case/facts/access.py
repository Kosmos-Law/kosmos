"""What may be attached to a matter's facts and highlights.

The URL's own ids are checked for matter membership centrally (see
apps/accounts/middleware.py). Ids posted in the body are not: a source or a
label named there must belong to the same matter as the thing it is being
attached to, or a user limited to one matter could reach into another.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.case.models import Document, Highlight, Label


def labels_for_matter(matter):
    """The labels a matter's material may carry: its own and the global ones."""
    return Label.objects.filter(Q(matter=None) | Q(matter=matter))


def label_for_matter(matter, label_id):
    """The label, or 404 when it is another matter's (or not a label id)."""
    if not str(label_id or "").isdigit():
        label_id = None
    return get_object_or_404(labels_for_matter(matter), pk=label_id)


def highlights_for_matter(matter):
    """Highlights on the matter's documents and saved cases."""
    return Highlight.objects.filter(
        Q(document__matter=matter) | Q(caselaw__matter=matter)
    )


def source_for_fact(fact, source_type, source_id):
    """The document or highlight named as a fact's source, or 404 when it
    is not on the fact's own matter. None for an unknown source type."""
    if not str(source_id or "").isdigit():
        source_id = None
    if source_type == "document":
        return get_object_or_404(Document, pk=source_id, matter_id=fact.matter_id)
    if source_type == "highlight":
        return get_object_or_404(highlights_for_matter(fact.matter_id), pk=source_id)
    return None
