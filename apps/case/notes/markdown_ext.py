"""Markdown extension for rendering note references."""

import re
from html import escape

from django.urls import reverse
from markdown import Extension
from markdown.preprocessors import Preprocessor

from apps.case.models import Document, Highlight


class NoteReferencePreprocessor(Preprocessor):
    """Convert [[doc:id|label]] and [[hl:id|label]] to links.

    The link is ours, so it is put in Markdown's HTML stash, which is
    written out as it stands even when the renderer treats markup in the
    text as text. What goes inside it (the label, a document's name, a
    highlight's words) is not ours, and is escaped."""

    DOC_PATTERN = re.compile(r"\[\[doc:(\d+)\|([^\]]+)\]\]")
    HL_PATTERN = re.compile(r"\[\[hl:(\d+)\|([^\]]+)\]\]")

    def run(self, lines):
        new_lines = []
        for line in lines:
            line = self.DOC_PATTERN.sub(self._replace_document, line)
            line = self.HL_PATTERN.sub(self._replace_highlight, line)
            new_lines.append(line)
        return new_lines

    def _replace_document(self, match):
        doc_id = int(match.group(1))
        label = match.group(2)

        try:
            document = Document.objects.get(pk=doc_id)
            citation = document.citation
            return self._stash(
                f'<a href="{reverse("case:viewer", args=[doc_id])}" '
                f'target="_blank" class="note-ref note-ref-document" '
                f'title="{escape(document.name or "")}">'
                f"{escape(label)} {escape(citation)}</a>"
            )
        except Document.DoesNotExist:
            return self._stash(
                '<span class="note-ref note-ref-missing">[Missing document]</span>'
            )

    def _replace_highlight(self, match):
        hl_id = int(match.group(1))
        label = match.group(2)

        try:
            highlight = Highlight.objects.select_related("document").get(pk=hl_id)
            citation = highlight.citation
            # A highlight opens in its document's viewer, at the highlight.
            if highlight.document_id:
                viewer = reverse("case:viewer", args=[highlight.document_id])
                href = f"{viewer}?highlight={hl_id}"
            else:
                href = reverse("case:highlight-detail", args=[hl_id])
            return self._stash(
                f'<a href="{href}" '
                f'target="_blank" class="note-ref note-ref-highlight" '
                f'title="{escape((highlight.text or "")[:100])}...">'
                f"{escape(label)} {escape(citation)}</a>"
            )
        except Highlight.DoesNotExist:
            return self._stash(
                '<span class="note-ref note-ref-missing">[Missing highlight]</span>'
            )

    def _stash(self, markup):
        return self.md.htmlStash.store(markup)


class NoteReferenceExtension(Extension):
    """Markdown extension to render note references."""

    def extendMarkdown(self, md):
        md.preprocessors.register(
            NoteReferencePreprocessor(md), "note_references", priority=25
        )


def makeExtension(**kwargs):
    return NoteReferenceExtension(**kwargs)
