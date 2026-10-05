"""The matter and proceeding statuses are declared once, on the models. The
forms, the list filter and the access modules' matter choices all read them
there, so one list cannot drift from another."""

from apps.activity.access import ENTRY_FORM_STATUSES
from apps.calendar.access import EVENT_MATTER_STATUSES
from apps.matters.filter import MatterFilter
from apps.matters.forms import MatterForm
from apps.matters.models import Matter
from apps.matters.proceedings.forms import ProceedingForm
from apps.matters.proceedings.models import Proceeding
from apps.settings.users.views import ASSIGNABLE_STATUSES
from apps.tasks.access import TASK_MATTER_STATUSES


def test_the_matter_form_and_filter_offer_the_models_statuses():
    assert MatterForm.Meta.STATUSES == Matter.STATUS_CHOICES
    assert tuple(MatterFilter.base_filters["status"].extra["choices"]) == (
        Matter.STATUS_CHOICES
    )
    assert [value for value, _ in Matter.STATUS_CHOICES] == list(Matter.STATUSES)


def test_the_proceeding_form_offers_the_models_statuses():
    assert ProceedingForm.Meta.STATUSES == Proceeding.STATUS_CHOICES
    assert [value for value, _ in Proceeding.STATUS_CHOICES] == list(
        Proceeding.STATUSES
    )


def test_active_and_inactive_split_the_lifecycle():
    assert Matter.ACTIVE_STATUSES + Matter.INACTIVE_STATUSES == Matter.STATUSES


def test_the_access_modules_draw_on_the_model():
    assert TASK_MATTER_STATUSES is Matter.ACTIVE_STATUSES
    assert EVENT_MATTER_STATUSES is Matter.ACTIVE_STATUSES
    assert ASSIGNABLE_STATUSES is Matter.ACTIVE_STATUSES
    assert set(ENTRY_FORM_STATUSES) == set(Matter.STATUSES) - {"Closed"}
