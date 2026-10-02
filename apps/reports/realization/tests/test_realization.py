"""Where the Realization report puts each dollar of time.

Work on an invoice that has not been sent is still work in progress, as it
is everywhere else; time marked Entered was billed outside Kosmos and is
left out; an invoice marked Paid from before payments were applied to
invoices is collected in full.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.activity.flat_fees.models import FlatFeeEntry
from apps.activity.time.models import TimeEntry
from apps.invoicing.invoices.models import Invoice
from apps.matters.models import Matter
from apps.reports.realization.aggregation import build_realization_context

pytestmark = pytest.mark.django_db


@pytest.fixture
def last_month():
    """A day in the last complete month, which the report's window ends on."""
    first_of_this_month = timezone.localdate().replace(day=1)
    return (first_of_this_month - timezone.timedelta(days=1)).replace(day=10)


@pytest.fixture
def timekeeper():
    return CustomUser.objects.create(username="Tess")


@pytest.fixture
def matter():
    return Matter.objects.create(name="Rivera v. Northside Logistics", status="Open")


def _time(user, matter, day, invoice=None, **extra):
    return TimeEntry.objects.create(
        user=user,
        matter=matter,
        date=day,
        actions="Work",
        hours=1,
        rate=100,
        invoice=invoice,
        **extra,
    )


def _invoice(matter, day, status):
    return Invoice.objects.create(
        matter=matter, date_limit=day, date_issued=day, status=status
    )


def _totals():
    context = build_realization_context(SimpleNamespace(session={}))
    return {row["label"]: row["total"] for row in context["realization_rows"]}


@pytest.mark.parametrize("status", ["DRAFT", "APPROVED"])
def test_work_on_an_unsent_invoice_is_unbilled(timekeeper, matter, last_month, status):
    _time(timekeeper, matter, last_month, invoice=_invoice(matter, last_month, status))

    totals = _totals()

    assert totals == {"Unbilled (WIP)": Decimal("100")}


def test_work_on_a_sent_invoice_is_outstanding(timekeeper, matter, last_month):
    _time(timekeeper, matter, last_month, invoice=_invoice(matter, last_month, "SENT"))

    assert _totals() == {"Outstanding": Decimal("100")}


def test_time_marked_entered_is_left_out(timekeeper, matter, last_month):
    _time(timekeeper, matter, last_month, entered=True)
    _time(timekeeper, matter, last_month)

    assert _totals() == {"Unbilled (WIP)": Decimal("100")}


def test_a_paid_invoice_with_nothing_applied_counts_as_collected(
    timekeeper, matter, last_month
):
    _time(timekeeper, matter, last_month, invoice=_invoice(matter, last_month, "PAID"))

    assert _totals() == {"Collected": Decimal("100")}


def test_a_comp_flat_fee_does_not_pull_the_hourly_rate_down(
    timekeeper, matter, last_month
):
    _time(timekeeper, matter, last_month, invoice=_invoice(matter, last_month, "PAID"))
    FlatFeeEntry.objects.create(
        user=timekeeper,
        matter=matter,
        date=last_month,
        description="Courtesy",
        amount=Decimal("400"),
        comp=True,
    )

    context = build_realization_context(SimpleNamespace(session={}))

    assert context["overall_realization"] == Decimal("100")
