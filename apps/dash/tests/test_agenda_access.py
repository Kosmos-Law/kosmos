"""The Plan (agenda) chat gives a user only what they could open themselves.

Its context names intakes, and names matters beside tasks, events and time
entries. Intakes need the Intakes permission; a row on a matter needs access
to that matter; rows on no matter are the firm's and reach everyone.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.activity.time.models import TimeEntry
from apps.calendar.models import Event
from apps.dash.agenda import _agenda_context
from apps.intakes.models import Intake
from apps.matters.models import Matter
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def assigned_matter():
    return Matter.objects.create(name="Assigned Boundary Dispute", status="Open")


@pytest.fixture
def hidden_matter():
    return Matter.objects.create(name="Confidential Merger", status="Open")


@pytest.fixture
def restricted(assigned_matter):
    """Limited to assigned matters, assigned only ``assigned_matter``."""
    user = CustomUser.objects.create(
        username="rae",
        first_name="Rae",
        last_name="Lee",
        email="rae@example.com",
        perm_all_matters=False,
    )
    assigned_matter.members.add(user)
    return user


@pytest.fixture
def admin():
    return CustomUser.objects.create(
        username="boss", email="boss@example.com", role="ADMIN"
    )


class TestIntakes:
    @pytest.fixture(autouse=True)
    def _intake(self):
        Intake.objects.create(
            name="Prospect Pat", status="Open", date=timezone.localdate()
        )

    def test_withheld_without_the_intakes_permission(self):
        user = CustomUser.objects.create(
            username="no-intakes", email="no-intakes@example.com", perm_intakes=False
        )
        context = _agenda_context(user)
        assert "Prospect Pat" not in context
        assert "OPEN INTAKES" not in context
        assert "/intakes/" not in context

    def test_given_with_the_intakes_permission(self):
        user = CustomUser.objects.create(
            username="intakes", email="intakes@example.com", perm_intakes=True
        )
        assert "Prospect Pat" in _agenda_context(user)

    def test_admin_passes_whatever_the_flag_says(self):
        user = CustomUser.objects.create(
            username="boss",
            email="boss@example.com",
            role="ADMIN",
            perm_intakes=False,
        )
        assert "Prospect Pat" in _agenda_context(user)


class TestMatterRows:
    def test_unassigned_task_on_a_hidden_matter_is_withheld(
        self, restricted, hidden_matter, assigned_matter
    ):
        Task.objects.create(
            description="File the merger notice", status="Pending", matter=hidden_matter
        )
        Task.objects.create(
            description="Order the survey", status="Pending", matter=assigned_matter
        )
        Task.objects.create(description="Renew the bar dues", status="Pending")

        context = _agenda_context(restricted)
        assert "File the merger notice" not in context
        assert "Confidential Merger" not in context
        assert "Order the survey" in context
        # A task on no matter is the firm's own.
        assert "Renew the bar dues" in context

    def test_own_task_on_a_hidden_matter_is_withheld(self, restricted, hidden_matter):
        """Assigned before the user was taken off the matter: the task
        list would not show it either."""
        Task.objects.create(
            description="Draft the disclosure",
            status="Pending",
            matter=hidden_matter,
            user=restricted,
        )
        context = _agenda_context(restricted)
        assert "Draft the disclosure" not in context
        assert "Confidential Merger" not in context

    def test_events_on_a_hidden_matter_are_withheld(
        self, restricted, hidden_matter, assigned_matter
    ):
        soon = timezone.localdate() + timedelta(days=3)
        Event.objects.create(
            description="Merger closing",
            status="Pending",
            date=soon,
            matter=hidden_matter,
        )
        Event.objects.create(
            description="Site inspection",
            status="Pending",
            date=soon,
            matter=assigned_matter,
        )
        Event.objects.create(description="Firm lunch", status="Pending", date=soon)

        context = _agenda_context(restricted)
        assert "Merger closing" not in context
        assert "Confidential Merger" not in context
        assert "Site inspection" in context
        assert "Firm lunch" in context

    def test_time_entries_on_a_hidden_matter_are_withheld(
        self, restricted, hidden_matter, assigned_matter
    ):
        yesterday = timezone.localdate() - timedelta(days=1)
        TimeEntry.objects.create(
            date=yesterday,
            matter=hidden_matter,
            user=restricted,
            actions="Reviewed the term sheet",
            hours=1,
        )
        TimeEntry.objects.create(
            date=yesterday,
            matter=assigned_matter,
            user=restricted,
            actions="Called the surveyor",
            hours=1,
        )
        context = _agenda_context(restricted)
        assert "Reviewed the term sheet" not in context
        assert "Confidential Merger" not in context
        assert "Called the surveyor" in context

    def test_admin_sees_every_matter(self, admin, hidden_matter):
        Task.objects.create(
            description="File the merger notice", status="Pending", matter=hidden_matter
        )
        context = _agenda_context(admin)
        assert "File the merger notice" in context
        assert "Confidential Merger" in context

    def test_user_with_all_matters_keeps_unassigned_work(self, hidden_matter):
        user = CustomUser.objects.create(
            username="everyone", email="everyone@example.com", perm_all_matters=True
        )
        Task.objects.create(
            description="File the merger notice", status="Pending", matter=hidden_matter
        )
        assert "File the merger notice" in _agenda_context(user)
