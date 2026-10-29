"""The Link Folder dialog and the Files status page."""

import pytest
from django.urls import reverse

from apps.drive.models import FilesState, MatterFolder, PdfFile

pytestmark = pytest.mark.django_db

SMITH = "Matters - Open/Smith v Jones"


def test_modal_lists_folders_with_the_name_match_suggested_first(
    admin_client, firm_root, matter
):
    content = admin_client.get(
        reverse("drive:folder-link-modal", args=[matter.id])
    ).content.decode()
    assert content.index("Smith v Jones") < content.index("Anderson Collection")
    assert "suggested" in content
    assert "0 Archive" not in content
    assert "2020-2022" not in content


def test_modal_marks_a_folder_another_matter_holds(
    admin_client, firm_root, matter, matter2
):
    MatterFolder.objects.create(matter=matter2, path="Matters - Open/Doe v Roe")
    content = admin_client.get(
        reverse("drive:folder-link-modal", args=[matter.id])
    ).content.decode()
    assert "linked to Doe v Roe" in content


def test_modal_does_not_name_a_matter_the_user_is_not_on(
    restricted_client, restricted_user, firm_root, matter, matter2
):
    matter.members.add(restricted_user)
    MatterFolder.objects.create(matter=matter2, path="Matters - Open/Doe v Roe")
    content = restricted_client.get(
        reverse("drive:folder-link-modal", args=[matter.id])
    ).content.decode()
    assert "linked to another matter" in content
    assert "Doe v Roe</span>" not in content


def test_modal_without_a_synced_tree_explains(admin_client, settings, matter):
    settings.DROPBOX_FIRM_ROOT = None
    content = admin_client.get(
        reverse("drive:folder-link-modal", args=[matter.id])
    ).content.decode()
    assert "aren't synced to this server" in content


def test_link_stores_the_folder_and_refreshes_state(
    admin_client, admin_user, firm_root, matter
):
    response = admin_client.post(
        reverse("drive:folder-link", args=[matter.id]), {"path": SMITH}
    )
    assert response.status_code == 204
    folder = MatterFolder.objects.get(matter=matter)
    assert folder.path == SMITH
    assert folder.linked_by == admin_user
    assert folder.absolute_path() == firm_root / SMITH
    assert SMITH not in FilesState.get().unclaimed_folders


def test_link_refuses_nothing_an_unknown_path_and_a_clash(
    admin_client, firm_root, matter, matter2
):
    url = reverse("drive:folder-link", args=[matter.id])
    assert b"Choose a folder" in admin_client.post(url, {"path": ""}).content
    assert (
        b"not under a matter root"
        in admin_client.post(url, {"path": "Matters - Closed/2020-2022"}).content
    )
    MatterFolder.objects.create(matter=matter2, path=SMITH)
    assert (
        b"already linked to Doe v Roe"
        in admin_client.post(url, {"path": SMITH}).content
    )
    assert not MatterFolder.objects.filter(matter=matter).exists()


def test_relinking_replaces_the_path(admin_client, firm_root, matter):
    MatterFolder.objects.create(matter=matter, path="Matters - Open/Doe v Roe")
    admin_client.post(reverse("drive:folder-link", args=[matter.id]), {"path": SMITH})
    assert MatterFolder.objects.get(matter=matter).path == SMITH


def test_unlink_removes_the_link_only(admin_client, firm_root, matter):
    MatterFolder.objects.create(matter=matter, path=SMITH)
    response = admin_client.post(reverse("drive:folder-unlink", args=[matter.id]))
    assert response.status_code == 204
    assert not MatterFolder.objects.filter(matter=matter).exists()
    assert (firm_root / SMITH).is_dir()


def test_a_user_off_the_matter_cannot_open_the_dialog(
    restricted_client, firm_root, matter
):
    response = restricted_client.get(
        reverse("drive:folder-link-modal", args=[matter.id])
    )
    assert response.status_code == 403


def test_the_ai_tab_shows_the_folder_chip_only_when_configured(
    admin_client, firm_root, matter, settings
):
    MatterFolder.objects.create(matter=matter, path=SMITH)
    content = admin_client.get(reverse("ai:list", args=[matter.id])).content.decode()
    assert "folder-chip-unlinked" not in content
    assert "Smith v Jones" in content
    settings.DROPBOX_FIRM_ROOT = None
    content = admin_client.get(reverse("ai:list", args=[matter.id])).content.decode()
    assert "ai-folder" not in content


def test_status_page_is_for_admins_and_lists_what_the_watcher_found(
    admin_client, restricted_client, firm_root, matter
):
    PdfFile.objects.create(
        path=f"{SMITH}/scan.pdf",
        size=10,
        has_text=False,
        ocr_status="failed",
        ocr_error="tesseract exploded",
    )
    MatterFolder.objects.create(matter=matter, path="Matters - Open/Gone")
    from apps.drive.watcher import refresh_links

    refresh_links()

    assert restricted_client.get(reverse("drive:files-status")).status_code == 403
    content = admin_client.get(reverse("drive:files-status")).content.decode()
    assert "Never reported" in content
    assert "Not scanned yet" in content
    assert "1 failed" in content
    assert "tesseract exploded" in content
    assert "Matters - Open/Gone" in content
    assert "Matters - Open/Doe v Roe" in content


def test_status_page_keeps_empty_files_out_of_the_failure_list(admin_client, firm_root):
    PdfFile.objects.create(path="Admin/empty.pdf", size=0, ocr_status="failed")
    PdfFile.objects.create(path="Admin/bad.pdf", size=10, ocr_status="failed")
    content = admin_client.get(reverse("drive:files-status")).content.decode()
    assert "Admin/bad.pdf" in content
    assert "Admin/empty.pdf" not in content
