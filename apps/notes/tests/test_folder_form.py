"""The folder form's wording: headed for what it is, and no em dashes."""

import pytest
from django.urls import reverse

from apps.notes.models import NoteFolder

pytestmark = pytest.mark.django_db


class TestFolderForm:
    def test_new_folder_form_is_headed_new_folder(self, client):
        html = client.get(reverse("notes:folder-add") + "?context=tab").content.decode()
        title = " ".join(
            html.split('<h1 class="modal-title">')[1].split("</h1>")[0].split()
        )
        assert title == "New Folder"

    def test_edit_form_is_headed_edit_folder(self, client):
        folder = NoteFolder.objects.create(name="Forms")
        html = client.get(
            reverse("notes:folder-edit", args=[folder.id])
        ).content.decode()
        title = " ".join(
            html.split('<h1 class="modal-title">')[1].split("</h1>")[0].split()
        )
        assert title == "Edit Folder"

    def test_root_choice_has_no_em_dashes(self, client):
        html = client.get(reverse("notes:folder-add") + "?context=tab").content.decode()
        assert '<option value="" selected>None (root level)</option>' in html
        assert "—" not in html
