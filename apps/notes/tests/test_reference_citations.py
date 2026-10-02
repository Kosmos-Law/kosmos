"""The citation labels a note may ask for.

A citation carries its document's name, so the labels are limited to the
documents and highlights of the note's own matter, and to users who may
see that note.
"""

import pytest
from django.urls import reverse

from apps.case.models import Document, Highlight
from apps.notes.models import Note

pytestmark = pytest.mark.django_db


def _document(matter, user, name):
    return Document.objects.create(
        matter=matter, name=name, category="Evidence", created_by=user
    )


def _highlight(document, user):
    return Highlight.objects.create(
        document=document, slug="hl", text="x", created_by=user, importance=4
    )


@pytest.fixture
def own_doc(matter, user):
    return _document(matter, user, "Deposition of Smith")


@pytest.fixture
def other_doc(other_matter, user):
    return _document(other_matter, user, "Confidential Settlement Memo")


def _citations(client, note, docs=(), highlights=()):
    query = "&".join([f"doc={d}" for d in docs] + [f"hl={h}" for h in highlights])
    return client.get(reverse("notes:note-citations", args=[note.id]) + "?" + query)


def test_labels_for_the_notes_own_matter(client, user, note, own_doc):
    hl = _highlight(own_doc, user)
    data = _citations(client, note, [own_doc.id], [hl.id]).json()
    assert data == {f"doc:{own_doc.id}": own_doc.citation, f"hl:{hl.id}": hl.citation}


def test_no_labels_for_another_matters_records(
    restricted_client, user, note, own_doc, other_doc
):
    other_hl = _highlight(other_doc, user)
    resp = _citations(
        restricted_client, note, [own_doc.id, other_doc.id], [other_hl.id]
    )
    assert resp.status_code == 200
    assert resp.json() == {f"doc:{own_doc.id}": own_doc.citation}
    assert b"Settlement" not in resp.content


def test_the_matter_limit_holds_for_users_who_see_every_matter(client, note, other_doc):
    assert _citations(client, note, [other_doc.id]).json() == {}


def test_library_note_gets_no_labels(restricted_client, user, own_doc, other_doc):
    library_note = Note.objects.create(author=user, title="Library Note")
    resp = _citations(restricted_client, library_note, [own_doc.id, other_doc.id])
    assert resp.json() == {}


def test_note_on_another_matter_is_refused(
    restricted_client, user, other_matter, other_doc
):
    other_note = Note.objects.create(author=user, matter=other_matter, title="Theirs")
    resp = _citations(restricted_client, other_note, [other_doc.id])
    assert resp.status_code == 404


def test_ids_that_are_not_numbers_are_ignored(client, note, own_doc):
    resp = _citations(client, note, [own_doc.id, "abc", ""], ["1 OR 1=1"])
    assert resp.status_code == 200
    assert resp.json() == {f"doc:{own_doc.id}": own_doc.citation}
