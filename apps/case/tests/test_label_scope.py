"""Every label list on a matter's tabs offers the same set: the global
labels and that matter's own.

A highlight on a saved case used to resolve to no matter (only
``highlight.document`` was consulted), so its apply modal offered only
global labels; and the Labels filter was built over every matter's labels.
"""

import pytest
from django.urls import reverse

from apps.case.models import Label
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_matter(user, contact, practice_area):
    return Matter.objects.create(
        user=user,
        name="Other Matter",
        status="Open",
        date_start="2024-01-01",
        practice_area=practice_area,
        client=contact,
    )


@pytest.fixture
def foreign_label(other_matter):
    return Label.objects.create(matter=other_matter, name="Foreign", color="red")


def test_highlight_modal_offers_the_matters_labels(
    client, highlight, label, global_label, foreign_label
):
    response = client.get(
        reverse("case:labels-apply-modal", args=["highlight", highlight.id])
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert label.name in body
    assert global_label.name in body
    assert foreign_label.name not in body


def test_labels_filter_is_scoped_to_the_matter(
    client_with_matter, matter, other_matter, label, global_label, foreign_label
):
    response = client_with_matter.get(reverse("case:filter-labels", args=[matter.id]))

    assert response.status_code == 200
    offered = set(response.context["filter"].qs)
    assert offered == {label, global_label}
    matter_choices = set(response.context["filter"].form.fields["matter"].queryset)
    assert matter_choices == {matter}


def test_labels_filter_stays_scoped_with_a_stored_filter(
    client_with_matter, matter, label, global_label, foreign_label
):
    client_with_matter.post(
        reverse("case:filter-labels", args=[matter.id]), {"order_by": "name"}
    )

    response = client_with_matter.get(reverse("case:filter-labels", args=[matter.id]))

    assert set(response.context["filter"].qs) == {label, global_label}
