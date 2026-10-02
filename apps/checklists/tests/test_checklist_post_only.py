"""A link cannot delete a template item or a checklist folder: those views
answer only to POST or DELETE."""

import pytest
from django.urls import reverse

from apps.checklists.models import (
    ChecklistFolder,
    ChecklistTemplate,
    ChecklistTemplateItem,
)

pytestmark = pytest.mark.django_db


def test_template_item_delete_is_post_only(client, template):
    item = template.items.first()
    url = reverse("checklists:delete-template-item", args=[item.id])
    assert client.get(url).status_code == 405
    assert ChecklistTemplateItem.objects.filter(pk=item.id).exists()
    # The item rows send hx-post.
    assert client.post(url).status_code == 200
    assert not ChecklistTemplateItem.objects.filter(pk=item.id).exists()


def test_folder_delete_refuses_get(client, template):
    folder = ChecklistFolder.objects.create(name="Litigation")
    template.folder = folder
    template.save()
    url = reverse("checklists:folder-delete", args=[folder.id])
    assert client.get(url + "?delete_templates=true").status_code == 405
    assert ChecklistFolder.objects.filter(pk=folder.id).exists()
    assert ChecklistTemplate.objects.filter(pk=template.id).exists()


def test_folder_delete_answers_to_delete_and_reads_its_options(client, template):
    """The confirm dialog sends hx-delete with its choices in the query string."""
    folder = ChecklistFolder.objects.create(name="Litigation")
    template.folder = folder
    template.save()
    url = reverse("checklists:folder-delete", args=[folder.id])

    assert client.delete(url + "?delete_templates=true").status_code == 204
    assert not ChecklistFolder.objects.filter(pk=folder.id).exists()
    assert not ChecklistTemplate.objects.filter(pk=template.id).exists()


def test_folder_delete_keeps_templates_unless_told(client, template):
    folder = ChecklistFolder.objects.create(name="Litigation")
    template.folder = folder
    template.save()
    url = reverse("checklists:folder-delete", args=[folder.id])
    assert client.post(url).status_code == 204
    template.refresh_from_db()
    assert template.folder is None
