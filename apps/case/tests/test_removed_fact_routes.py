"""Addresses that were removed because nothing linked to them.

The matter-level timeline routes rendered templates that do not exist
(every page request was a server error) and its delete acted on a plain
link for any fact id. The facts print page and the inline description
editor were likewise unreachable. They now answer 404."""

import pytest
from django.urls import NoReverseMatch, reverse

from apps.case.models import Fact

pytestmark = pytest.mark.django_db


def test_matter_timeline_addresses_are_gone(client, matter, fact):
    for path in (
        f"/matters/{matter.id}/timeline/",
        f"/matters/{matter.id}/timeline/list/",
        f"/matters/{matter.id}/timeline/add",
        f"/matters/{matter.id}/timeline/{fact.id}/edit",
        f"/matters/{matter.id}/timeline/{fact.id}/delete",
        f"/matters/{matter.id}/timeline/print",
        f"/matters/{matter.id}/timeline/pdf/",
        f"/matters/{matter.id}/timeline/{fact.id}/edit-description",
        f"/matters/{matter.id}/timeline/{fact.id}/edit-citations",
    ):
        assert client.get(path).status_code == 404, path

    assert Fact.objects.filter(pk=fact.pk).exists()


def test_unreachable_facts_addresses_are_gone(client, matter, fact):
    for path in (
        f"/case/{matter.id}/facts/print/",
        f"/case/facts/{fact.id}/edit-description/",
        f"/case/facts/{fact.id}/update-description/",
    ):
        assert client.get(path).status_code == 404, path

    for name in ("case:facts-print", "matters:timeline-index"):
        with pytest.raises(NoReverseMatch):
            reverse(name, args=[matter.id])


def test_the_timeline_pdf_is_still_served_from_the_facts_tab(client, matter, fact):
    assert reverse("case:facts-pdf", args=[matter.id]) in (
        client.get(f"/case/{matter.id}/facts/list/").content.decode()
    )
