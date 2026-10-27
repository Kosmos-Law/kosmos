"""Watson search registration for the case builder's models. Email is
registered by apps.mail; the firm-wide kinds by apps.search."""

from watson import search as watson

from apps.case.models import Document, Fact, Highlight
from apps.management.watson import TruncatingSearchAdapter

# Register Document model for search
watson.register(
    Document,
    adapter_cls=TruncatingSearchAdapter,
    fields=("name", "description", "ocr_text"),
)

# Register Highlight model for search
watson.register(
    Highlight,
    fields=("slug", "text"),
)

# Register Fact model for search
watson.register(
    Fact,
    fields=("description",),
)
