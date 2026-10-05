"""Restore Defaults in Filter Highlights puts the list back in its default
order, newest first.

The button used to store order_by "created" (oldest first), the opposite
of what a fresh session shows."""

import pytest
from django.urls import reverse

from apps.case.models import Highlight

pytestmark = pytest.mark.django_db


def _ids(client, matter):
    response = client.get(reverse("case:highlights-list", args=[matter.id]))
    return [h.id for h in response.context["highlights"]]


def test_restore_defaults_is_newest_first(client_with_matter, matter, document, user):
    older = Highlight.objects.create(
        document=document, slug="Older", text="a", page_number=1, created_by=user
    )
    newer = Highlight.objects.create(
        document=document, slug="Newer", text="b", page_number=1, created_by=user
    )
    client_with_matter.get(
        reverse("case:highlights-filter-sort", args=[matter.id, "created"])
    )
    assert _ids(client_with_matter, matter) == [older.id, newer.id]

    response = client_with_matter.get(
        reverse("case:highlights-filter-default", args=[matter.id])
    )

    assert response.status_code == 302
    assert client_with_matter.session[f"highlights_filter_{matter.id}"] == {}
    assert _ids(client_with_matter, matter) == [newer.id, older.id]
