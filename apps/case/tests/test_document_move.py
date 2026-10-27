"""Moving documents to another matter, by bulk move or by Edit Details."""

import pytest
from django.urls import reverse

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


def _select(client, matter, *documents):
    session = client.session
    session[f"selected_documents_{matter.id}"] = [d.id for d in documents]
    session.save()


def _bulk_move(client, matter, target):
    return client.post(
        reverse("case:documents-bulk-matter", args=[matter.id]), {"matter": target.id}
    )


def _edit_data(document, matter_id=None):
    data = {
        "category": document.category,
        "name": document.name,
        "description": "",
        "date": "2024-01-20",
        "ai_context": "auto",
    }
    if matter_id is not None:
        data["matter"] = matter_id
    return data


# ── Bulk move ────────────────────────────────────────────────────────────


def test_bulk_move_moves_the_documents_without_a_warning(
    client, matter, other_matter, document
):
    _select(client, matter, document)

    response = _bulk_move(client, matter, other_matter)

    assert "HX-Toast" not in response
    document.refresh_from_db()
    assert document.matter_id == other_matter.id


# ── Edit Details ─────────────────────────────────────────────────────────


def test_edit_details_offers_the_matter(client, matter, document):
    response = client.get(reverse("case:documents-edit", args=[document.id]))

    assert response.context["form"].fields["matter"].disabled is False


def test_edit_details_moves_a_document(client, matter, other_matter, document):
    response = client.post(
        reverse("case:documents-edit", args=[document.id]),
        _edit_data(document, other_matter.id),
    )

    assert response.status_code == 204
    document.refresh_from_db()
    assert document.matter_id == other_matter.id
