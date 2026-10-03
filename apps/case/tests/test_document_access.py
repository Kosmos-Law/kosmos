"""Matters reached from the Documents tab other than the one in the URL: the
Matter list in Edit Details, the duplicate warning, the bulk move target and
the proceeding set from the row menu. The central check on /case/ routes
sees none of these."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.case.models import Document
from apps.matters.models import Matter
from apps.matters.proceedings.models import Proceeding

from .test_document_fingerprint import make_pdf

pytestmark = pytest.mark.django_db


@pytest.fixture
def restricted_user(matter):
    user = CustomUser.objects.create(
        username="restricted", email="restricted@example.com", perm_all_matters=False
    )
    user.set_password("pw")
    user.save()
    matter.members.add(user)
    return user


@pytest.fixture
def restricted_client(restricted_user):
    client = Client()
    client.login(username="restricted", password="pw")
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


@pytest.fixture
def other_matter(user, contact, practice_area):
    """An Open matter the restricted user is not on. Sorts first by name."""
    return Matter.objects.create(
        user=user,
        name="AAA Other Matter",
        status="Open",
        date_start="2024-01-01",
        practice_area=practice_area,
        client=contact,
    )


def _select(client, matter, document):
    session = client.session
    session[f"selected_documents_{matter.id}"] = [document.id]
    session.save()


def _edit_data(document, matter_id):
    return {
        "matter": matter_id,
        "category": document.category,
        "name": document.name,
        "description": document.description or "",
        "date": "2024-01-20",
        "ai_context": "auto",
    }


# ── Edit Details: the Matter list ────────────────────────────────────────


def test_edit_keeps_a_closed_matter_in_the_list_and_selected(
    client, matter, other_matter, document
):
    matter.status = "Closed"
    matter.save()

    response = client.get(reverse("case:documents-edit", args=[document.id]))

    form = response.context["form"]
    assert matter in form.fields["matter"].queryset
    assert form["matter"].value() == matter.id
    assert f'<option value="{matter.id}" selected>' in response.content.decode()


def test_saving_edit_details_leaves_a_closed_matters_document_where_it_is(
    client, matter, other_matter, document
):
    matter.status = "Closed"
    matter.save()

    # What the browser submits: the selected option, which is now the
    # document's own matter rather than the first Open one.
    form = client.get(reverse("case:documents-edit", args=[document.id])).context[
        "form"
    ]
    response = client.post(
        reverse("case:documents-edit", args=[document.id]),
        _edit_data(document, form["matter"].value()),
    )

    assert response.status_code == 204
    document.refresh_from_db()
    assert document.matter_id == matter.id


def test_edit_matter_list_is_limited_to_the_users_matters(
    restricted_client, matter, other_matter, document
):
    response = restricted_client.get(reverse("case:documents-edit", args=[document.id]))

    choices = list(response.context["form"].fields["matter"].queryset)
    assert choices == [matter]


def test_edit_cannot_move_a_document_to_a_matter_the_user_is_not_on(
    restricted_client, matter, other_matter, document
):
    response = restricted_client.post(
        reverse("case:documents-edit", args=[document.id]),
        _edit_data(document, other_matter.id),
    )

    assert response.status_code == 200  # the form comes back with an error
    document.refresh_from_db()
    assert document.matter_id == matter.id


def test_add_on_a_closed_matter_offers_that_matter(client, matter, other_matter):
    matter.status = "Closed"
    matter.save()

    response = client.get(reverse("case:documents-add", args=[matter.id]))

    assert matter in response.context["form"].fields["matter"].queryset


# ── Duplicate warning ────────────────────────────────────────────────────


def _upload(client, matter, pdf_bytes):
    return client.post(
        reverse("case:documents-add", args=[matter.id]),
        {
            "matter": matter.id,
            "category": "Evidence",
            "name": "Upload",
            "ai_context": "auto",
            "file": SimpleUploadedFile(
                "x.pdf", pdf_bytes, content_type="application/pdf"
            ),
        },
    )


def _existing(matter, user, name):
    doc = Document(matter=matter, name=name, category="Evidence", created_by=user)
    doc.save()
    doc.file.save("a.pdf", io.BytesIO(make_pdf()), save=True)
    return doc


def test_duplicate_warning_leaves_out_matters_the_user_is_not_on(
    restricted_client, user, matter, other_matter
):
    _existing(other_matter, user, "Privileged Memo")

    response = _upload(restricted_client, matter, make_pdf())

    # No match the user may see: no warning, the upload goes through.
    assert response.status_code == 204
    assert Document.objects.filter(matter=matter).count() == 1


def test_duplicate_warning_shows_matches_on_the_users_matters(
    restricted_client, restricted_user, user, matter, other_matter
):
    _existing(other_matter, user, "Privileged Memo")
    _existing(matter, user, "Our Copy")

    response = _upload(restricted_client, matter, make_pdf())

    body = response.content.decode()
    assert response.status_code == 200
    assert "Our Copy" in body
    assert "Privileged Memo" not in body
    assert other_matter.name not in body


def test_duplicate_warning_on_edit_leaves_out_other_matters(
    restricted_client, user, matter, other_matter, document
):
    _existing(other_matter, user, "Privileged Memo")

    data = _edit_data(document, matter.id)
    data["file"] = SimpleUploadedFile(
        "x.pdf", make_pdf(), content_type="application/pdf"
    )
    response = restricted_client.post(
        reverse("case:documents-edit", args=[document.id]), data
    )

    assert response.status_code == 204
    assert b"Privileged Memo" not in response.content


def test_user_with_all_matters_still_sees_every_match(
    client, user, matter, other_matter
):
    _existing(other_matter, user, "Elsewhere")

    response = _upload(client, matter, make_pdf())

    assert response.status_code == 200
    assert "Elsewhere" in response.content.decode()


# ── Bulk move ────────────────────────────────────────────────────────────


def test_bulk_move_to_a_matter_the_user_is_not_on_is_refused(
    restricted_client, matter, other_matter, document
):
    _select(restricted_client, matter, document)

    response = restricted_client.post(
        reverse("case:documents-bulk-matter", args=[matter.id]),
        {"matter": other_matter.id},
    )

    assert response.status_code == 403
    document.refresh_from_db()
    assert document.matter_id == matter.id


def test_bulk_move_clears_a_proceeding_of_the_old_matter(
    client, matter, other_matter, document, proceeding
):
    document.category = "Record"
    document.proceeding = proceeding
    document.save()
    _select(client, matter, document)

    response = client.post(
        reverse("case:documents-bulk-matter", args=[matter.id]),
        {"matter": other_matter.id},
    )

    assert response.status_code == 204
    document.refresh_from_db()
    assert document.matter_id == other_matter.id
    assert document.proceeding is None


def test_bulk_move_dialog_asks_for_confirmation(client, matter, other_matter, document):
    _select(client, matter, document)

    body = client.get(
        reverse("case:documents-bulk-matter", args=[matter.id])
    ).content.decode()

    assert "hx-confirm=" in body
    assert "Move 1 document to the selected matter?" in body


# ── Proceeding from the row menu ─────────────────────────────────────────


def test_proceeding_of_another_matter_is_refused(
    client, user, matter, other_matter, document
):
    foreign = Proceeding.objects.create(
        user=user,
        matter=other_matter,
        date_filed="2024-01-15",
        forum="District Court",
        case_number="2024CV999",
        status="Pending",
    )

    response = client.post(
        reverse("case:document-proceeding", args=[document.id, foreign.id])
    )

    assert response.status_code == 404
    document.refresh_from_db()
    assert document.proceeding is None


def test_proceeding_of_the_documents_matter_is_set(client, document, proceeding):
    response = client.post(
        reverse("case:document-proceeding", args=[document.id, proceeding.id])
    )

    assert response.status_code == 200
    document.refresh_from_db()
    assert document.proceeding == proceeding
