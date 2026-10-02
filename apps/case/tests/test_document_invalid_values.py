"""A value the Documents tab cannot use is refused (400), not a server
error."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_unknown_category_is_refused(client, document):
    response = client.post(
        reverse("case:document-category", args=[document.id, "Pleadings"])
    )

    assert response.status_code == 400
    document.refresh_from_db()
    assert document.category == "Evidence"


@pytest.mark.parametrize("importance", [0, 8, 99])
def test_importance_outside_the_scale_is_refused(client, document, importance):
    response = client.post(
        reverse("case:document-importance", args=[document.id, importance])
    )

    assert response.status_code == 400
    document.refresh_from_db()
    assert document.importance == 4


def test_bulk_move_to_a_matter_value_that_is_not_an_id_is_refused(
    client, matter, document
):
    session = client.session
    session[f"selected_documents_{matter.id}"] = [document.id]
    session.save()

    response = client.post(
        reverse("case:documents-bulk-matter", args=[matter.id]), {"matter": "abc"}
    )

    assert response.status_code == 400
    document.refresh_from_db()
    assert document.matter_id == matter.id
