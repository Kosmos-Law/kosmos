"""What the case app registers at start-up: its own tabs in the case shell,
the material kinds of the semantic index, and the matter lookups the
access middleware resolves its routes with. Called from CaseConfig.ready().
"""

from django.db.models import Q

from apps.accounts.access import register_matter_lookup
from apps.case import semantic, tabs


def register():
    from apps.case.caselaws.views import get_caselaws_data
    from apps.case.documents.views import get_document_data
    from apps.case.facts.views import get_facts_data
    from apps.case.highlights.views import get_highlights_data
    from apps.case.labels.views import get_label_data
    from apps.case.models import CaseLaw, Document, Fact, Highlight, Label, Witness
    from apps.case.search.views import get_search_data
    from apps.case.witnesses.views import get_witnesses_data
    from apps.settings.ai import ai_enabled
    from apps.settings.courtlistener import caselaw_available

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
    # 60 is the Emails tab (apps.mail), 90 the AI tab (apps.ai).
    tab("labels", "Labels", 70, lambda r, m: get_label_data(r, m.id))
    tab("search", "Search", 80, lambda r, m: get_search_data(r, m, m.id))
    # Saved case law: its own tab when AI is off and CourtListener is on,
    # a view inside the AI tab otherwise (the AI tab claims it as active).
    tab(
        "caselaws",
        "Case Law",
        95,
        lambda r, m: get_caselaws_data(r, m, m.id),
        available=lambda user, matter_id: caselaw_available(user),
        listed=lambda user, matter_id: caselaw_available(user) and not ai_enabled(),
    )

    register_matter_lookup("document_id", Document, ("matter_id",), "document")
    register_matter_lookup(
        "highlight_id",
        Highlight,
        ("document__matter_id", "caselaw__matter_id"),
        "highlight",
    )
    register_matter_lookup("caselaw_id", CaseLaw, ("matter_id",), "caselaw")
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
        source = highlight.document or highlight.caselaw
        matter_id = source.matter_id if source else None
        return matter_id, f"{highlight.citation}\n{highlight.text or ''}"

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
            Q(document__matter=matter) | Q(caselaw__matter=matter)
        ).select_related("document", "caselaw"),
    )
    semantic.register_kind(
        "fact",
        Fact,
        lambda fact: (fact.matter_id, fact.description or ""),
        backfill=lambda matter: Fact.objects.filter(matter=matter),
    )
