"""The checklist folder form's wording."""

import pytest

from apps.checklists.forms import ChecklistFolderForm

pytestmark = pytest.mark.django_db


def test_root_folder_choice_has_no_em_dash():
    assert ChecklistFolderForm().fields["parent"].empty_label == "None (root level)"
