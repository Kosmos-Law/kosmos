"""The Intakes report counts every intake in its window, under the firm's
own practice areas. (Its columns were once a fixed list of one firm's
areas: an intake under any other area was missing from the table, and the
status table took its total from that table.)"""

from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.intakes.models import Intake
from apps.matters.models import PracticeArea
from apps.reports.intakes.aggregation import UNSPECIFIED, build_intakes_context

pytestmark = pytest.mark.django_db


def _context():
    return build_intakes_context(SimpleNamespace(session={}))


def test_every_intake_is_in_both_tables():
    today = timezone.localdate()
    area = PracticeArea.objects.create(name="Maritime Zed", is_active=True)
    retired = PracticeArea.objects.create(name="Retired Zed", is_active=False)
    Intake.objects.create(name="One", date=today, status="Open", practice_area=area)
    Intake.objects.create(
        name="Two", date=today, status="Accepted", practice_area=retired
    )
    Intake.objects.create(name="Three", date=today, status="Open")

    context = _context()

    assert "Maritime Zed" in context["practice_areas"]
    assert "Retired Zed" in context["practice_areas"]
    assert context["practice_areas"][-1] == UNSPECIFIED
    assert context["total_intakes"] == 3
    assert context["totals_by_practice_area"]["Maritime Zed"] == 1
    assert context["totals_by_practice_area"][UNSPECIFIED] == 1
    assert sum(context["totals_by_status"].values()) == 3
    assert context["totals_by_status"]["Open"] == 2
    assert context["percentages_by_status"]["Accepted"] == 33.3
    this_month = context["intake_data"][-1]
    assert this_month["total"] == 3
    assert this_month["practice_areas"]["Retired Zed"] == 1


def test_an_empty_window_still_shows_the_firms_practice_areas():
    PracticeArea.objects.create(name="Maritime Zed", is_active=True)

    context = _context()

    assert "Maritime Zed" in context["practice_areas"]
    assert UNSPECIFIED not in context["practice_areas"]
    assert context["total_intakes"] == 0
    assert context["percentages_by_status"] == {}
