"""The Documents tab's Drive button on a firm without Google Drive.

Hidden while Drive isn't connected and the matter has no Drive folder or
mappings; kept when either exists, so a link made earlier can still be seen
and undone after a disconnect.
"""

import pytest

from apps.drive import mappings
from apps.drive.models import DriveFolderMapping
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def bare_matter(db):
    return Matter.objects.create(name="Doe v Roe", status="Open")


@pytest.fixture
def drive_off(monkeypatch):
    monkeypatch.setattr("apps.drive.google.check_credentials", lambda: False)


@pytest.fixture
def drive_on(monkeypatch):
    monkeypatch.setattr("apps.drive.google.check_credentials", lambda: True)


def _documents(client, matter):
    return client.get(f"/case/{matter.id}/tab/documents/").content.decode()


def test_status_hides_without_drive_or_link(bare_matter, drive_off):
    status = mappings.matter_drive_status(bare_matter)
    assert status["connected"] is False
    assert status["show"] is False


def test_status_shows_when_connected(bare_matter, drive_on):
    assert mappings.matter_drive_status(bare_matter)["show"] is True


def test_status_shows_for_a_linked_matter(matter, drive_off):
    assert mappings.matter_drive_status(matter)["show"] is True


def test_status_shows_for_leftover_mappings(bare_matter, drive_off):
    DriveFolderMapping.objects.create(
        matter=bare_matter,
        folder_id="f1",
        folder_path="Corr",
        category="Correspondence",
    )
    assert mappings.matter_drive_status(bare_matter)["show"] is True


def test_documents_tab_hides_link_button(client, bare_matter, drive_off):
    assert "Link Drive Folder" not in _documents(client, bare_matter)


def test_documents_tab_shows_link_button_when_connected(client, bare_matter, drive_on):
    assert "Link Drive Folder" in _documents(client, bare_matter)


def test_documents_tab_keeps_button_for_linked_matter(client, matter, drive_off):
    assert "Drive Folder" in _documents(client, matter)
