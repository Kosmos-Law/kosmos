"""What Add Event and Edit Event accept, and how the form opens.

A blank description is a form error, not a server error. The description
limit is the column's. An event with a start and no end gets an end on the
same day. A click on a calendar time slot opens the form on that day and
time, and a form opened from a matter keeps that matter whatever its status.
"""

from datetime import date, time

import pytest
from django.urls import reverse

from apps.calendar.events import default_end_time
from apps.calendar.forms import EventForm
from apps.calendar.models import Event
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


def _data(**changes):
    return {
        "date": "2030-03-04",
        "party": "Client",
        "status": "Pending",
        "description": "Hearing on motion",
    } | changes


# --- description -----------------------------------------------------------


def test_blank_description_is_a_form_error(client):
    response = client.post(reverse("calendar:add"), _data(description=""))

    assert response.status_code == 200
    assert "4 or more" in response.context["form"].errors["description"][0]


def test_description_may_fill_the_column():
    assert EventForm(_data(description="a" * 255)).is_valid()


def test_description_past_the_column_names_the_real_limit():
    form = EventForm(_data(description="a" * 256))

    assert form.errors["description"] == ["Description is limited to 255 characters."]


# --- the end time given to a start with no end -----------------------------


@pytest.mark.parametrize(
    "start, end",
    [
        (time(9, 0), time(10, 0)),
        (time(22, 59), time(23, 59)),
        (time(23, 30), time(23, 59)),
        (time(23, 59), None),
    ],
)
def test_default_end_time_stays_on_the_same_day(start, end):
    assert default_end_time(start) == end


def test_late_start_saves_with_an_end_after_it(client, matter):
    client.post(reverse("calendar:add"), _data(matter=matter.id, start_time="23:30"))

    event = Event.objects.get(description="Hearing on motion")
    assert event.start_time == time(23, 30)
    assert event.end_time == time(23, 59)


def test_edit_gives_a_late_start_an_end_after_it(client, event, matter):
    client.post(
        reverse("calendar:edit", args=[event.id]),
        _data(matter=matter.id, start_time="23:45"),
    )

    event.refresh_from_db()
    assert event.end_time > event.start_time


# --- opening the form from the calendar ------------------------------------


def test_time_slot_click_carries_the_date_and_the_start_time(client):
    form = client.get(
        reverse("calendar:add"), {"date": "2030-03-04", "start_time": "14:30"}
    ).context["form"]

    assert form.initial["date"] == date(2030, 3, 4)
    assert form.initial["start_time"] == time(14, 30)


def test_a_date_time_in_the_date_still_lands_on_that_day(client):
    form = client.get(
        reverse("calendar:add"), {"date": "2030-03-04T14:30:00-05:00"}
    ).context["form"]

    assert form.initial["date"] == date(2030, 3, 4)


def test_day_click_carries_no_start_time(client):
    form = client.get(reverse("calendar:add"), {"date": "2030-03-04"}).context["form"]

    assert form.initial["date"] == date(2030, 3, 4)
    assert "start_time" not in form.initial


# --- opening the form from a matter ----------------------------------------


@pytest.mark.parametrize("status", ["Complete", "Closed"])
def test_form_opened_from_an_inactive_matter_keeps_that_matter(
    client, practice_area, status
):
    done = Matter.objects.create(
        name="Finished Matter", status=status, practice_area=practice_area
    )
    url = reverse("calendar:add-matter-origin", args=[done.id, "matters"])

    response = client.get(url)

    assert done in response.context["form"].fields["matter"].queryset
    action = response.context["action"]
    client.post(action, _data(matter=done.id))
    assert Event.objects.get(description="Hearing on motion").matter == done


def test_inactive_matters_are_otherwise_left_out(client, matter, practice_area):
    done = Matter.objects.create(
        name="Finished Matter", status="Closed", practice_area=practice_area
    )

    form = client.get(reverse("calendar:add")).context["form"]

    assert matter in form.fields["matter"].queryset
    assert done not in form.fields["matter"].queryset
