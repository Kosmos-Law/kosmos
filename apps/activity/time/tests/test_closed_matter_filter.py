"""Closed matters must stay filterable on the Activity tabs.

The matter choices only carry Pending/Open/Complete, so "View in Activity
Tab" on a closed matter used to fail validation and django-filter silently
dropped the constraint, showing every matter's entries.
include_selected_matter (apps/activity/filters.py) appends the bound
matter to the choices whatever its status.
"""

import pytest
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.activity.time.models import TimeEntry
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def closed_matter(practice_area):
    return Matter.objects.create(
        name="Closed Test Matter",
        work_status="Awaiting response from OC",
        status="Closed",
        practice_area=practice_area,
    )


def make_entry(user, matter):
    return TimeEntry.objects.create(
        user_id=user.id,
        matter=matter,
        date="2020-01-07",
        actions="Call with client",
        hours=0.2,
        rate=300,
        comp=False,
        entered=False,
    )


def test_view_in_activity_tab_filters_to_closed_matter(
    client, user, matter, closed_matter
):
    on_closed = make_entry(user, closed_matter)
    on_open = make_entry(user, matter)

    response = client.get(
        reverse("activity:time-filter-matter", args=[closed_matter.id]),
        follow=True,
    )
    assert response.status_code == 200

    objects = list(response.context["objects"])
    assert on_closed in objects
    assert on_open not in objects


def test_filter_modal_offers_the_bound_closed_matter(client, user, closed_matter):
    session = client.session
    session["time_filter"] = {"matter": closed_matter.id, "order_by": "-date"}
    session.save()

    response = client.get(reverse("activity:time-filter"))
    assert response.status_code == 200
    matter_field = response.context["filter"].form.fields["matter"]
    assert matter_field.queryset.filter(pk=closed_matter.id).exists()


def test_view_in_activity_tab_clears_toolbar_overrides(client, user, matter):
    """The toolbar's date preset and user chip must not narrow the matter view."""
    colleague = CustomUser.objects.create(
        username="Colleague", email="colleague@example.com", user_rate=100
    )
    mine = make_entry(user, matter)
    theirs = make_entry(colleague, matter)

    session = client.session
    session["time_filter"] = {
        "filter_label": "today",
        "date_min": "2026-10-17",
        "date_max": "2026-10-17",
        "user": user.id,
        "order_by": "-date",
    }
    session.save()

    response = client.get(
        reverse("activity:time-filter-matter", args=[matter.id]), follow=True
    )
    assert response.status_code == 200

    objects = list(response.context["objects"])
    assert mine in objects
    assert theirs in objects
    stored = client.session["time_filter"]
    assert stored["filter_label"] == "all"
    assert "user" not in stored
