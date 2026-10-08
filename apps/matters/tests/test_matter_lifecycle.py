"""Closing, reopening, filtering, editing and deleting a matter."""

import importlib
from datetime import date

import pytest
from django.apps import apps as django_apps
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.activity.time.models import TimeEntry
from apps.invoicing.invoices.models import Invoice
from apps.matters.filter import MatterFilter
from apps.matters.models import Matter, PracticeArea
from apps.matters.proceedings.models import Proceeding
from apps.matters.rates.models import Rate

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(user):
    user.role = "ADMIN"
    user.save()
    client = Client()
    client.force_login(user)
    client.get("/dash/")
    return client


def _proceeding(user, matter, status):
    return Proceeding.objects.create(
        user=user,
        matter=matter,
        date_filed="2020-08-07",
        forum="Example Superior",
        case_number=f"20CV-{status}",
        status=status,
    )


# --- closing and reopening --------------------------------------------------


@pytest.mark.parametrize("status", ["Complete", "Closed"])
def test_closing_records_the_date_and_concludes_open_proceedings(user, matter, status):
    matter.date_end = None
    matter.save()
    ongoing = _proceeding(user, matter, "Ongoing")
    stayed = _proceeding(user, matter, "Stayed")
    dismissed = _proceeding(user, matter, "Dismissed")

    matter.status = status
    matter.save()

    matter.refresh_from_db()
    assert matter.date_end == timezone.localdate()
    assert Proceeding.objects.get(pk=ongoing.pk).status == "Concluded"
    assert Proceeding.objects.get(pk=stayed.pk).status == "Concluded"
    assert Proceeding.objects.get(pk=dismissed.pk).status == "Dismissed"


def test_saving_a_closed_matter_again_leaves_its_proceedings_alone(user, matter):
    matter.status = "Closed"
    matter.save()
    reopened_case = _proceeding(user, matter, "Ongoing")
    closed_on = Matter.objects.get(pk=matter.pk).date_end

    matter.work_status = "File archived"
    matter.save()

    assert Proceeding.objects.get(pk=reopened_case.pk).status == "Ongoing"
    assert Matter.objects.get(pk=matter.pk).date_end == closed_on


def test_complete_to_closed_keeps_the_first_closing_date(matter):
    matter.status = "Complete"
    matter.save()
    Matter.objects.filter(pk=matter.pk).update(date_end=date(2021, 3, 1))
    matter.refresh_from_db()

    matter.status = "Closed"
    matter.save()

    assert Matter.objects.get(pk=matter.pk).date_end == date(2021, 3, 1)


def test_reopening_clears_the_closing_date(matter):
    matter.status = "Closed"
    matter.save()

    matter.status = "Open"
    matter.save()

    assert Matter.objects.get(pk=matter.pk).date_end is None


def test_closing_date_is_written_when_only_named_fields_are_saved(matter):
    Matter.objects.filter(pk=matter.pk).update(date_end=None)
    matter.refresh_from_db()

    matter.status = "Closed"
    matter.save(update_fields=["status"])

    assert Matter.objects.get(pk=matter.pk).date_end == timezone.localdate()


def test_backfill_gives_closed_matters_their_closing_date(matter):
    matter.status = "Complete"
    matter.save()
    matter.status = "Closed"
    matter.save()
    first_closed = (
        matter.history.filter(status="Complete").order_by("history_date").first()
    )
    Matter.objects.filter(pk=matter.pk).update(date_end=None)

    migration = importlib.import_module(
        "apps.matters.migrations.0054_backfill_matter_date_end"
    )
    migration.backfill_date_end(django_apps, None)

    expected = timezone.localtime(first_closed.history_date).date()
    assert Matter.objects.get(pk=matter.pk).date_end == expected


# --- the list's filter and sort ----------------------------------------------


def test_practice_area_filter_uses_the_firms_own_list(matter, practice_area):
    other_area = PracticeArea.objects.create(name="Probate", is_active=True)
    other = Matter.objects.create(
        name="Estate of Example", status="Open", practice_area=other_area
    )

    form_choices = MatterFilter().form.fields["practice_area"].queryset
    assert {practice_area, other_area} <= set(form_choices)

    found = MatterFilter({"practice_area": str(other_area.id)}).qs
    assert list(found) == [other]


def test_a_stale_practice_area_name_in_the_session_is_ignored(client, matter):
    session = client.session
    session["matter_filter"] = {"status": "Open", "practice_area": "General"}
    session.save()

    response = client.get(reverse("matters:index"))

    assert response.status_code == 200


def test_closed_on_or_before_finds_closed_matters(matter):
    matter.date_end = None
    matter.status = "Closed"
    matter.save()

    today = timezone.localdate().isoformat()
    assert matter in MatterFilter({"date_end": today}).qs
    assert matter not in MatterFilter({"date_end": "2000-01-01"}).qs


def test_work_status_sort_button_sorts_by_work_status(client, matter, practice_area):
    Matter.objects.create(
        name="Zeta Holdings",
        status="Open",
        work_status="A first",
        practice_area=practice_area,
    )

    client.post(reverse("matters:order-by", args=["work_status"]))
    response = client.get(reverse("matters:index"))

    assert response.context["current_order"] == "work_status"
    assert [m.name for m in response.context["matters"]] == [
        "Zeta Holdings",
        "Sample Test Matter",
    ]
    assert b"order-by/work_status" in response.content


# --- adding and editing ------------------------------------------------------


def test_a_restricted_user_can_open_the_matter_they_add(practice_area):
    user = CustomUser.objects.create(
        username="Rae", email="rae@example.com", perm_all_matters=False
    )
    user.set_password("clawboy")
    user.save()
    client = Client()
    client.force_login(user)
    client.get("/dash/")

    response = client.post(
        reverse("matters:add"),
        {
            "status": "Pending",
            "date_start": "2024-01-02",
            "name": "Rivera v. Northside Logistics",
            "billable": "True",
            "billing_type": "HOURLY",
            "deferred_fee": "False",
        },
    )

    assert response.status_code == 204, response.context["form"].errors
    matter = Matter.objects.get(name="Rivera v. Northside Logistics")
    assert user.has_matter_access(matter)


def test_new_contact_from_the_edit_form_returns_to_that_matter(client, matter, folder):
    client.post(
        reverse("matters:client-new-contact"),
        {"matter_id": matter.id, "name": "Renamed Matter", "status": "Open"},
    )

    response = client.post(
        reverse("matters:client-create-contact"),
        {"name": "Elena Rivera", "folder": folder.id},
    )

    assert response.status_code == 200
    assert response.context["edit"] is True
    assert response.context["action"] == f"/matters/{matter.id}/edit"
    assert response.context["form"].instance == matter
    assert response.context["form"].initial["name"] == "Renamed Matter"
    assert f'name="matter_id" value="{matter.id}"'.encode() in response.content


def test_cancelling_the_detour_from_the_add_form_returns_an_add_form(client):
    client.post(reverse("matters:client-new-contact"), {"name": "New Matter"})

    response = client.post(reverse("matters:client-cancel"))

    assert response.context["add"] is True
    assert response.context["action"] == "/matters/add"


# --- deleting -----------------------------------------------------------------


def test_deleting_a_matter_deletes_its_invoices(admin_client, user, matter):
    invoice = Invoice.objects.create(
        matter=matter, date_limit=date(2020, 1, 31), date_issued=date(2020, 1, 1)
    )
    TimeEntry.objects.create(
        user=user,
        matter=matter,
        date="2020-01-07",
        actions="Call",
        hours=1,
        rate=100,
        invoice=invoice,
    )

    response = admin_client.delete(f"/matters/{matter.id}/delete")

    assert response.status_code == 204
    assert not Matter.objects.filter(pk=matter.pk).exists()
    assert not Invoice.objects.filter(pk=invoice.pk).exists()


# --- rates ----------------------------------------------------------------------


def test_a_user_gets_one_rate_per_matter(client, user, matter):
    Rate.objects.create(matter=matter, user=user, matter_rate=250)
    url = reverse("matters:rates-add", args=[matter.id])

    offered = client.get(url).context["form"].fields["user"].queryset
    assert user not in offered

    response = client.post(url, {"user": user.id, "matter_rate": 300})

    assert response.status_code == 200
    assert response.context["form"].errors
    assert Rate.objects.filter(matter=matter, user=user).count() == 1


# --- the matter's Time list ------------------------------------------------------


def test_time_list_sorts_by_date_not_by_entry_order(client, user, matter):
    TimeEntry.objects.create(
        user=user,
        matter=matter,
        date="2020-03-01",
        actions="Entered first, done later",
        hours=1,
        rate=100,
    )
    TimeEntry.objects.create(
        user=user,
        matter=matter,
        date="2020-01-01",
        actions="Entered second, done earlier",
        hours=1,
        rate=100,
    )
    url = reverse("matters:activity", args=[matter.id])

    newest_first = [str(e.date) for e in client.get(url).context["entries"]]
    client.post(reverse("matters:activity-sort", args=[matter.id]))
    oldest_first = [str(e.date) for e in client.get(url).context["entries"]]

    assert newest_first == ["2020-03-01", "2020-01-01"]
    assert oldest_first == ["2020-01-01", "2020-03-01"]


def test_moving_and_comping_on_a_matter_need_the_financial_permission(user, matter):
    user.perm_financial = False
    user.save()
    client = Client()
    client.force_login(user)
    client.get("/dash/")
    entry = TimeEntry.objects.create(
        user=user, matter=matter, date="2020-01-07", actions="Call", hours=1, rate=100
    )
    client.post(reverse("matters:activity-toggle-select", args=[matter.id, entry.id]))

    comp = client.post(
        reverse("matters:activity-bulk-update-comp", args=[matter.id]), {"comp": "true"}
    )
    move = client.post(
        reverse("matters:activity-bulk-update-matter", args=[matter.id]),
        {"matter": matter.id},
    )

    assert comp.status_code == 403
    assert move.status_code == 403
    assert TimeEntry.objects.get(pk=entry.pk).comp is False
    body = client.get(reverse("matters:activity", args=[matter.id])).content
    assert b"/activity/bulk/update-comp" not in body
    assert b"/activity/bulk/update-matter" not in body
    assert b"/activity/bulk/set-category" in body
