"""Settings > Features: the firm's administrator switches the case file
off for everyone. Off, the sidebar and the matter header lose their
entries and the paths answer 404. The data stays.
Notes are retired: their pages are gone whatever the switches say."""

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


def test_the_case_file_is_on_by_default(admin_client, matter):
    body = admin_client.get("/matters/").content.decode()
    assert 'id="nav-case"' in body
    assert admin_client.get(f"/case/{matter.id}/documents/").status_code == 200


def test_the_form_has_no_library_switch(admin_client):
    body = admin_client.get(reverse("settings:features-index")).content.decode()
    assert "Library" not in body


def test_saving_the_form_switches_the_features(admin_client):
    response = admin_client.post(
        reverse("settings:features-index"),
        {"case_file_enabled": "False", "accounting_enabled": "True"},
    )
    assert response.status_code == 200
    assert "Feature settings updated" in response.headers["HX-Toast"]
    firm = Firm.objects.get()
    assert firm.case_file_enabled is False
    assert firm.accounting_enabled is True


def test_case_file_off_hides_and_refuses_the_case_file(admin_client, matter):
    _switch(case_file_enabled=False)

    body = admin_client.get("/matters/").content.decode()
    assert 'id="nav-case"' not in body
    record = admin_client.get(f"/matters/{matter.id}", follow=True).content.decode()
    assert f'href="/case/select-matter/{matter.id}/"' not in record
    assert admin_client.get("/case/").status_code == 404
    assert admin_client.get(f"/case/{matter.id}/documents/").status_code == 404
    assert admin_client.get(f"/case/{matter.id}/tab/ai/").status_code == 404


def test_case_file_off_keeps_the_mcp_api(admin_client, matter):
    _switch(case_file_enabled=False)
    # The middleware lets these through; the API itself wants a token.
    assert (
        admin_client.get(f"/case/api/matter/{matter.id}/overview/").status_code == 401
    )
    assert admin_client.get("/case/api/matters/").status_code == 401


def test_the_notes_are_gone(admin_client, matter):
    body = admin_client.get("/matters/").content.decode()
    assert 'id="nav-notes"' not in body
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


def test_the_firm_wide_search_has_no_notes(admin_client):
    body = admin_client.get(reverse("search:search")).content.decode()
    assert "Notes" not in body
