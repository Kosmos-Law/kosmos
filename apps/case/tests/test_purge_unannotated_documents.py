"""purge_unannotated_documents: documents with no highlight, fact, note or
promoted email are deleted with their files; the rest stay."""

import io

import pytest
from django.core.files.storage import default_storage
from django.core.management import call_command

from apps.case.models import Document, Fact, Highlight, Label, MaterialChunk
from apps.mail.models import Email

pytestmark = pytest.mark.django_db


def _doc(matter, user, name, **fields):
    doc = Document(
        matter=matter, name=name, category="Evidence", created_by=user, **fields
    )
    doc.save()
    doc.file.save(f"{doc.pk}.pdf", io.BytesIO(b"%PDF-1.4 " + name.encode()), save=True)
    return doc


def _run(*args):
    out = io.StringIO()
    call_command("purge_unannotated_documents", *args, stdout=out, stderr=io.StringIO())
    return out.getvalue()


@pytest.fixture
def docs(matter, user):
    highlighted = _doc(matter, user, "Highlighted")
    Highlight.objects.create(
        document=highlighted, slug="hl", text="x", created_by=user, importance=4
    )
    cited = _doc(matter, user, "Cited")
    fact = Fact.objects.create(matter=matter, date="2024-01-25", description="d")
    fact.documents.add(cited)
    promoted = _doc(matter, user, "Promoted")
    Email.objects.create(
        matter=matter, gmail_id="m1", thread_id="t1", document=promoted
    )
    labelled = _doc(matter, user, "Labelled only", description="Hand-written")
    labelled.labels.add(Label.objects.create(matter=matter, name="Key"))
    bare = _doc(matter, user, "Bare")
    return {
        "keep": [highlighted, cited, promoted],
        "drop": [labelled, bare],
    }


def test_dry_run_reports_and_deletes_nothing(docs, matter):
    out = _run("--list")
    assert f"Matter {matter.id} ({matter.name}): 2" in out
    assert "Bare" in out and "Labelled only" in out
    assert "Highlighted" not in out
    assert "2 unannotated document(s); 3 annotated document(s) stay." in out
    assert "Dry run" in out
    assert Document.objects.count() == 5


def test_apply_deletes_only_unannotated_documents_and_their_files(
    docs, django_capture_on_commit_callbacks
):
    paths = [d.file.name for d in docs["drop"]]
    assert all(default_storage.exists(p) for p in paths)
    MaterialChunk.objects.create(
        matter=docs["drop"][1].matter,
        kind="document",
        object_id=docs["drop"][1].pk,
        chunk_index=0,
        text="t",
        content_hash="h",
        embedding=[0.0] * 768,
    )

    with django_capture_on_commit_callbacks(execute=True):
        out = _run("--apply")

    assert "Removed 2 document(s)." in out
    assert set(Document.objects.values_list("pk", flat=True)) == {
        d.pk for d in docs["keep"]
    }
    assert not any(default_storage.exists(p) for p in paths)
    assert not MaterialChunk.objects.filter(kind="document").exists()
    assert all(default_storage.exists(d.file.name) for d in docs["keep"])


def test_matter_option_limits_the_purge(docs, matter, user, contact, practice_area):
    from apps.matters.models import Matter

    other = Matter.objects.create(
        user=user,
        name="Other",
        status="Open",
        date_start="2024-01-01",
        practice_area=practice_area,
        client=contact,
    )
    elsewhere = _doc(other, user, "Elsewhere")

    _run("--apply", "--matter", str(matter.id))

    assert Document.objects.filter(pk=elsewhere.pk).exists()
    assert Document.objects.count() == 4
