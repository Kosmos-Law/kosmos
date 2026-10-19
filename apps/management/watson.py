from watson import search as watson


class TruncatingSearchAdapter(watson.SearchAdapter):
    """Postgres caps a tsvector's input at 1MB; a huge text past it (an OCR
    body, a long email) aborts the row's index write, and a full
    buildwatson with it. The first ~900k characters carry the searchable
    substance."""

    max_content_chars = 900_000

    def get_content(self, obj):
        return super().get_content(obj)[: self.max_content_chars]
