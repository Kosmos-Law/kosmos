"""What the case app registers at start-up: its own tabs in the case shell,
the material kinds of the semantic index, and the matter lookups the
access middleware resolves its routes with. Called from CaseConfig.ready().
"""

from apps.accounts.access import register_matter_lookup
from apps.case import semantic, tabs


def register():
    from apps.case.documents.views import get_document_data
    from apps.case.facts.views import get_facts_data
    from apps.case.highlights.views import get_highlights_data
    from apps.case.labels.views import get_label_data
    from apps.case.models import Document, Fact, Highlight, Label, Witness
    from apps.case.search.views import get_search_data
    from apps.case.witnesses.views import get_witnesses_data

    def tab(name, label, order, data, **options):
        tabs.register(
            tabs.Tab(
                name=name,
                label=label,
                index_url=f"case:{name}-index",
                list_url=f"case:{name}-list",
                template=f"case/{name}/list.html",
                data=data,
                order=order,
                **options,
            )
        )

    tab("documents", "Documents", 10, lambda r, m: get_document_data(r, m.id))
    tab("highlights", "Highlights", 20, lambda r, m: get_highlights_data(r, m, m.id))
    tab("facts", "Timeline", 30, lambda r, m: get_facts_data(r, m, m.id))
    tab("witnesses", "Witnesses", 40, lambda r, m: get_witnesses_data(r, m, m.id))
    # 60 is the Emails tab (apps.mail).
    tab("labels", "Labels", 70, lambda r, m: get_label_data(r, m.id))
    tab("search", "Search", 80, lambda r, m: get_search_data(r, m, m.id))

    register_matter_lookup("document_id", Document, ("matter_id",), "document")
    register_matter_lookup(
        "highlight_id", Highlight, ("document__matter_id",), "highlight"
    )
    register_matter_lookup("fact_id", Fact, ("matter_id",), "fact")
    register_matter_lookup("witness_id", Witness, ("matter_id",), "witness")
    register_matter_lookup("label_id", Label, ("matter_id",))

    # Semantic index kinds. Email is registered by apps.mail.
    def document_source(doc):
        if doc.ai_context == "never" or doc.ocr_status not in (
            "completed",
            "extracted",
        ):
            return doc.matter_id, ""
        return (
            doc.matter_id,
            f"{doc.name}\n{doc.description or ''}\n{doc.ocr_text or ''}",
        )

    def highlight_source(highlight):
        return (
            highlight.document.matter_id,
            f"{highlight.citation}\n{highlight.text or ''}",
        )

    semantic.register_kind(
        "document",
        Document,
        document_source,
        backfill=lambda matter: Document.objects.filter(matter=matter),
    )
    semantic.register_kind(
        "highlight",
        Highlight,
        highlight_source,
        backfill=lambda matter: Highlight.objects.filter(
            document__matter=matter
        ).select_related("document"),
    )
    semantic.register_kind(
        "fact",
        Fact,
        lambda fact: (fact.matter_id, fact.description or ""),
        backfill=lambda matter: Fact.objects.filter(matter=matter),
    )
