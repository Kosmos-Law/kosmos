"""Settings > Features: the firm's administrator switches the case file and
the library off for everyone. Off, the sidebar and the matter header lose
their entries, the paths answer 404, the Notes tab and the notes search
scope disappear, and the Drive mirror pauses. The data stays."""

import pytest
from django.urls import reverse

from apps.contacts.models import Contact
from apps.folders.models import Folder
from apps.matters.models import Matter, PracticeArea
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db


@pytest.fixture
def matter(admin_client):
    folder = Folder.objects.create(name="Clients")
    contact = Contact.objects.create(name="Client", folder=folder)
    area = PracticeArea.objects.create(name="General")
    return Matter.objects.create(
        name="Test v. Case", client=contact, practice_area=area, status="Open"
    )


def _switch(**values):
    """Set the firm's switches; a test without a Firm row gets one."""
    firm = Firm.objects.first() or Firm.objects.create(name="Firm")
    for name, value in values.items():
        setattr(firm, name, value)
    firm.save()


def test_the_page_is_admin_only(client, admin_client):
    assert client.get(reverse("settings:features-index")).status_code == 403
    assert admin_client.get(reverse("settings:features-index")).status_code == 200


def test_both_features_are_on_by_default(admin_client, matter):
    body = admin_client.get("/matters/").content.decode()
    assert 'id="nav-case"' in body
    assert 'id="nav-notes"' in body
    assert admin_client.get(f"/case/{matter.id}/documents/").status_code == 200
    assert admin_client.get("/notes/").status_code == 200


def test_saving_the_form_switches_the_features(admin_client):
    response = admin_client.post(
        reverse("settings:features-index"),
        {"case_file_enabled": "False", "library_enabled": "True"},
    )
    assert response.status_code == 200
    assert "Feature settings updated" in response.headers["HX-Toast"]
    firm = Firm.objects.get()
    assert firm.case_file_enabled is False
    assert firm.library_enabled is True


def test_case_file_off_hides_and_refuses_the_case_file(admin_client, matter):
    _switch(case_file_enabled=False)

    body = admin_client.get("/matters/").content.decode()
    assert 'id="nav-case"' not in body
    assert 'id="nav-notes"' in body  # the library stays
    record = admin_client.get(f"/matters/{matter.id}", follow=True).content.decode()
    assert f'href="/case/select-matter/{matter.id}/"' not in record
    assert admin_client.get("/case/").status_code == 404
    assert admin_client.get(f"/case/{matter.id}/documents/").status_code == 404
    assert admin_client.get(f"/case/{matter.id}/tab/ai/").status_code == 404


def test_case_file_off_keeps_the_mcp_api_and_matter_notes(admin_client, matter):
    _switch(case_file_enabled=False)
    # The middleware lets these through; the API itself wants a token.
    assert (
        admin_client.get(f"/case/api/matter/{matter.id}/overview/").status_code == 401
    )
    assert admin_client.get(f"/case/{matter.id}/notes/list/").status_code == 200


def test_library_off_hides_and_refuses_the_notes(admin_client, matter):
    _switch(library_enabled=False)

    body = admin_client.get("/matters/").content.decode()
    assert 'id="nav-notes"' not in body
    assert 'id="nav-case"' in body
    assert admin_client.get("/notes/").status_code == 404
    assert admin_client.get(f"/case/{matter.id}/notes/").status_code == 404
    nav = admin_client.get(f"/case/{matter.id}/tab/documents/").content.decode()
    assert f"/case/{matter.id}/notes/" not in nav
    # A remembered Notes tab falls back to Documents.
    session = admin_client.session
    session[f"case_tab_{matter.id}"] = "notes"
    session.save()
    response = admin_client.get(f"/case/select-matter/{matter.id}/")
    assert response["Location"] == reverse("case:documents-index", args=[matter.id])


def test_library_off_drops_notes_from_the_firm_wide_search(admin_client):
    _switch(library_enabled=False)
    body = admin_client.get(reverse("search:search")).content.decode()
    assert "Notes" not in body


def test_both_off_drops_the_sidebar_rule(admin_client):
    _switch(case_file_enabled=False, library_enabled=False)
    body = admin_client.get("/matters/").content.decode()
    assert "sidebar-divider" not in body


def test_the_drive_mirror_pauses_with_the_case_file(db, monkeypatch):
    from apps.drive import google

    _switch(case_file_enabled=False)
    monkeypatch.setattr(google, "sync", lambda **kw: pytest.fail("sync ran"))
    assert google.scheduled_sync() == {"skipped": "case file off"}
    assert google.scheduled_sync_full() == {"skipped": "case file off"}
