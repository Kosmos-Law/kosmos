"""Restore Defaults in Filter Facts and Filter Witnesses clears the filter.

The filter is kept in the session per matter (facts_filter_<matter id>).
The button used to clear the bare key, which nothing reads, so it did
nothing."""

import re

import pytest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("tab", ["facts", "witnesses"])
def test_restore_defaults_clears_the_matters_filter(client, matter, tab):
    key = f"{tab}_filter_{matter.id}"
    client.post(f"/case/{matter.id}/{tab}/filter/", {"keyword": "contract"})
    assert client.session[key]["keyword"] == "contract"

    modal = client.get(f"/case/{matter.id}/{tab}/filter/").content.decode()
    restore = re.search(r'hx-post="(/[^"]*clear-filters/[^"]*)"', modal)
    assert restore, "the dialog has no Restore Defaults address"
    assert f"/{key}/" in restore.group(1)

    response = client.post(restore.group(1))

    assert response.status_code == 204
    assert client.session[key] == {}
