"""The website's intake push names the kind of dispute with a short key. It
is matched to one of the firm's own practice areas by name; nothing in the
code knows any firm's list.

Practice areas are named by each firm in Settings. A key that matches none
of them leaves the intake's practice area empty for staff to set.
"""

import json

import pytest
from django.test import Client

from apps.intakes.api_views import practice_area_for
from apps.intakes.models import Intake
from apps.matters.models import PracticeArea

pytestmark = pytest.mark.django_db

SEAM_KEY = "test-seam-key"


@pytest.fixture(autouse=True)
def only_these_areas(settings):
    """The test database carries seeded practice areas: start from none, so
    each test states the firm's list itself."""
    settings.KOSMOS_SEAM_KEY = SEAM_KEY
    PracticeArea.objects.all().delete()


def _area(name, **extra):
    return PracticeArea.objects.create(name=name, **extra)


@pytest.mark.parametrize(
    "sent, name",
    [
        ("boundary", "Boundary"),
        ("hoa", "HOA"),
        ("quiet_title", "Quiet Title"),
        ("quiet-title", "Quiet title"),
        ("Quiet Title", "quiet_title"),
        ("purchasesale", "Purchase / Sale"),
        (" landlord ", "Landlord"),
    ],
)
def test_a_key_finds_the_practice_area_of_the_same_name(sent, name):
    area = _area(name)
    _area("Something Else")

    assert practice_area_for(sent) == area


@pytest.mark.parametrize("sent", ["contract", "other", "title", "", None, 7, []])
def test_a_key_that_is_no_practice_areas_name_finds_nothing(sent):
    _area("Purchase / Sale")
    _area("General")
    _area("Quiet Title")

    assert practice_area_for(sent) is None


def test_an_inactive_practice_area_is_not_used():
    _area("Boundary", is_active=False)

    assert practice_area_for("boundary") is None


def test_no_firms_names_are_built_in():
    """With a firm whose practice areas are its own, the old built-in table
    would have looked for names this firm does not have."""
    family = _area("Family")
    _area("Probate")

    assert practice_area_for("family") == family
    assert practice_area_for("landlord") is None
    assert practice_area_for("tenant") is None


def _push(payload):
    return Client().post(
        "/api/receive-intake/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_SEAM_KEY=SEAM_KEY,
    )


def test_the_push_sets_the_matching_practice_area():
    area = _area("Quiet Title")

    response = _push(
        {"full_name": "Jane Roe", "report": "REPORT", "dispute_nature": "quiet_title"}
    )

    intake = Intake.objects.get(id=response.json()["intake_id"])
    assert intake.practice_area == area


def test_the_push_leaves_the_practice_area_empty_when_nothing_matches():
    _area("Title")

    response = _push(
        {"full_name": "Jane Roe", "report": "REPORT", "dispute_nature": "quiet_title"}
    )

    assert response.status_code == 200
    intake = Intake.objects.get(id=response.json()["intake_id"])
    assert intake.practice_area is None
