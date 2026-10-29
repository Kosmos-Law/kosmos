"""Which folders are matters, and what the picker suggests."""

import pytest

from apps.drive import tree
from apps.drive.models import MatterFolder

pytestmark = pytest.mark.django_db


def test_matter_folders_are_the_children_of_the_matter_roots(firm_root):
    assert tree.list_matter_folders() == [
        "Matters - Open/Anderson Collection",
        "Matters - Open/Doe v Roe",
        "Matters - Open/Smith v Jones",
        "Matters - Pending/New Intake",
    ]


def test_archive_closed_and_dropbox_folders_are_not_matters(firm_root):
    paths = tree.list_matter_folders()
    assert not any("0 Archive" in path for path in paths)
    assert not any(path.startswith("Matters - Closed") for path in paths)
    assert tree.is_ignored(".dropbox.cache/x.pdf")
    assert tree.is_ignored("Matters - Open/Smith v Jones/.~lock.brief.odt#")
    assert not tree.is_ignored("Matters - Open/Smith v Jones/Evidence/scan.pdf")


def test_not_configured_without_a_root(settings):
    settings.DROPBOX_FIRM_ROOT = None
    assert not tree.configured()
    assert tree.list_matter_folders() == []


def test_suggestion_is_the_exact_name_or_a_close_one(firm_root):
    paths = tree.list_matter_folders()
    assert tree.suggest("Smith v Jones", paths) == "Matters - Open/Smith v Jones"
    assert tree.suggest("smith v. jones", paths) == "Matters - Open/Smith v Jones"
    assert tree.suggest("Anderson Collections", paths) == (
        "Matters - Open/Anderson Collection"
    )


def test_no_suggestion_for_a_poor_match(firm_root):
    assert tree.suggest("Zebra Holdings LLC", tree.list_matter_folders()) is None
    assert tree.suggest("", tree.list_matter_folders()) is None


def test_unclaimed_folders_leave_out_linked_ones(firm_root, matter):
    MatterFolder.objects.create(matter=matter, path="Matters - Open/Smith v Jones")
    assert "Matters - Open/Smith v Jones" not in tree.unclaimed_folders()
    assert "Matters - Open/Doe v Roe" in tree.unclaimed_folders()
