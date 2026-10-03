"""Restore Defaults in Filter Documents and Filter Labels clears the filter
that is actually stored: the per-matter session key."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "prefix, filter_route, trigger",
    [
        ("documents_filter", "case:documents-filter", "documentsChanged"),
        ("labels_filter", "case:filter-labels", "labelsChanged"),
    ],
)
def test_restore_defaults_clears_the_matters_own_filter(
    client, matter, prefix, filter_route, trigger
):
    key = f"{prefix}_{matter.id}"
    session = client.session
    session[key] = {"keyword": "lease", "order_by": "name"}
    session.save()

    body = client.get(reverse(filter_route, args=[matter.id])).content.decode()
    restore_url = reverse(
        "management:clear-filters", kwargs={"session_key": key, "trigger": trigger}
    )
    assert f'hx-post="{restore_url}"' in body

    response = client.post(restore_url)

    assert response.status_code == 204
    assert response["HX-Trigger"] == trigger
    assert client.session[key] == {}
