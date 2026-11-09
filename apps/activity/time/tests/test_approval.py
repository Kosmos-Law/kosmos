"""Time entries the AI logs need a person's approval: the badge and its
Approve / Edit / Reject menu, the Needs Approval filter, and the bulk
Approve action that the entry's own user or an admin may run, on the
Activity tab and on a matter's Time list."""

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.activity.presets import activity_date_filters, detect_filter_label
from apps.activity.time.models import TimeEntry

pytestmark = pytest.mark.django_db


def select_time(client, ids, key="selected_time"):
    session = client.session
    session[key] = ids
    session.save()


@pytest.fixture
def colleague():
    return CustomUser.objects.create(
        username="Pat", email="pat@example.com", user_rate=100
    )


@pytest.fixture
def admin():
    return CustomUser.objects.create(
        username="Boss", email="boss@example.com", user_rate=100, role="ADMIN"
    )


@pytest.fixture
def flagged(user, matter):
    return TimeEntry.objects.create(
        user=user,
        matter=matter,
        date="2020-01-09",
        actions="AI logged this",
        hours=0.3,
        rate=300,
        needs_approval=True,
    )


@pytest.fixture
def colleagues_flagged(colleague, matter):
    return TimeEntry.objects.create(
        user=colleague,
        matter=matter,
        date="2020-01-09",
        actions="Pat's AI entry",
        hours=0.5,
        rate=300,
        needs_approval=True,
    )


def logged_in(user):
    client = Client()
    client.force_login(user)
    client.get("/dash/")
    return client


class TestBadgeAndFilter:
    def test_badge_shows_on_flagged_rows_only(self, client, flagged, entry):
        client.post(reverse("activity:time-filter-quick", args=["all"]))
        html = client.get(reverse("activity:time-list")).content.decode()
        assert html.count("Needs approval") == 1
        assert "AI logged this" in html and "Call with client" in html

    def test_selection_column_for_a_user_without_financial(self, user, flagged):
        user.perm_financial = False
        user.save()
        client = logged_in(user)
        client.post(reverse("activity:time-filter-quick", args=["all"]))
        html = client.get(reverse("activity:time-list")).content.decode()
        assert reverse("activity:time-toggle-select", args=[flagged.id]) in html
        assert reverse("activity:time-bulk-update-comp") not in html

    def test_needs_approval_quick_filter(self, client, flagged, entry):
        response = client.post(
            reverse("activity:time-filter-quick", args=["needs_approval"])
        )
        assert response.status_code == 204
        assert client.session["time_filter"]["filter_label"] == "needs_approval"
        html = client.get(reverse("activity:time-list")).content.decode()
        assert "AI logged this" in html and "Call with client" not in html

    def test_switching_away_clears_the_approval_override(self, client, flagged):
        client.post(reverse("activity:time-filter-quick", args=["needs_approval"]))
        client.post(reverse("activity:time-filter-quick", args=["all"]))
        assert "needs_approval" not in client.session["time_filter"]

    def test_label_detection(self):
        today = date(2026, 10, 30)
        preset = activity_date_filters(today)["needs_approval"]
        assert detect_filter_label(preset, today) == "needs_approval"


class TestBulkApproveOnActivityTab:
    url = reverse("activity:time-bulk-approve")

    def test_owner_approves_own(self, client, flagged):
        select_time(client, [flagged.id])
        response = client.post(self.url)
        assert response.status_code == 204
        flagged.refresh_from_db()
        assert flagged.needs_approval is False
        assert client.session.get("selected_time") in (None, [])

    def test_non_admin_cannot_approve_a_colleagues(
        self, client, flagged, colleagues_flagged
    ):
        select_time(client, [flagged.id, colleagues_flagged.id])
        response = client.post(self.url)
        assert response.status_code == 204
        flagged.refresh_from_db()
        colleagues_flagged.refresh_from_db()
        assert flagged.needs_approval is False
        assert colleagues_flagged.needs_approval is True
        assert "Approved 1 entry" in response["HX-Toast"]
        assert "not yours to approve" in response["HX-Toasts"]

    def test_admin_approves_anyones(self, admin, flagged, colleagues_flagged):
        client = logged_in(admin)
        select_time(client, [flagged.id, colleagues_flagged.id])
        assert client.post(self.url).status_code == 204
        assert not TimeEntry.objects.filter(needs_approval=True).exists()

    def test_nothing_selected_is_400(self, client, flagged):
        assert client.post(self.url).status_code == 400

    def test_entry_outside_the_users_matters_is_untouched(
        self, user, colleague, matter
    ):
        other = TimeEntry.objects.create(
            user=user,
            matter=matter,
            date="2020-01-09",
            actions="x",
            hours=1,
            rate=1,
            needs_approval=True,
        )
        user.perm_all_matters = False
        user.save()
        client = logged_in(user)
        select_time(client, [other.id])
        assert client.post(self.url).status_code == 204
        other.refresh_from_db()
        assert other.needs_approval is True


class TestBulkApproveOnMatter:
    def test_owner_approves_on_the_matter_list(self, client, matter, flagged):
        select_time(client, [flagged.id], key=f"selected_matter_activity_{matter.id}")
        response = client.post(
            reverse("matters:activity-bulk-approve", args=[matter.id])
        )
        assert response.status_code == 204
        flagged.refresh_from_db()
        assert flagged.needs_approval is False

    def test_badge_and_approve_button_on_the_matter_list(self, client, matter, flagged):
        url = reverse("matters:activity", args=[matter.id])
        html = client.get(url).content.decode()
        assert "Needs approval" in html
        # The bulk toolbar, Approve included, appears once something is selected
        select_time(client, [flagged.id], key=f"selected_matter_activity_{matter.id}")
        html = client.get(url).content.decode()
        assert reverse("matters:activity-bulk-approve", args=[matter.id]) in html


class TestBadgeMenu:
    def approve_url(self, entry):
        return reverse("activity:time-approve", args=[entry.id])

    def reject_url(self, entry):
        return reverse("activity:time-reject", args=[entry.id])

    def edit_url(self, entry):
        return reverse("activity:time-edit", args=[entry.id]) + "?approve=1"

    def form_data(self, entry, **changes):
        data = {
            "matter": entry.matter_id,
            "user": entry.user_id,
            "date": "2020-01-09",
            "actions": entry.actions,
            "hours": "0.3",
            "rate": "300",
            "entered": "2020-01-09",
        }
        data.update(changes)
        return data

    def test_menu_on_the_activity_tab(self, client, flagged):
        client.post(reverse("activity:time-filter-quick", args=["all"]))
        html = client.get(reverse("activity:time-list")).content.decode()
        assert self.approve_url(flagged) in html
        assert self.reject_url(flagged) in html
        assert "edit?approve=1" in html

    def test_menu_on_the_matter_list(self, client, matter, flagged):
        html = client.get(reverse("matters:activity", args=[matter.id])).content
        assert self.approve_url(flagged) in html.decode()

    def test_no_menu_on_a_colleagues_entry(self, client, colleagues_flagged):
        client.post(reverse("activity:time-filter-quick", args=["all"]))
        html = client.get(reverse("activity:time-list")).content.decode()
        assert "Needs approval" in html
        assert self.approve_url(colleagues_flagged) not in html

    def test_admin_gets_the_menu_on_anyones(self, admin, colleagues_flagged):
        client = logged_in(admin)
        client.post(reverse("activity:time-filter-quick", args=["all"]))
        html = client.get(reverse("activity:time-list")).content.decode()
        assert self.approve_url(colleagues_flagged) in html

    def test_approve(self, client, flagged):
        response = client.post(self.approve_url(flagged))
        assert response.status_code == 204
        assert response["HX-Trigger"] == "timeChanged"
        flagged.refresh_from_db()
        assert flagged.needs_approval is False

    def test_approve_a_colleagues_is_refused(self, client, colleagues_flagged):
        assert client.post(self.approve_url(colleagues_flagged)).status_code == 403
        colleagues_flagged.refresh_from_db()
        assert colleagues_flagged.needs_approval is True

    def test_approve_is_post_only(self, client, flagged):
        assert client.get(self.approve_url(flagged)).status_code == 405

    def test_reject_deletes(self, client, flagged):
        response = client.post(self.reject_url(flagged))
        assert response.status_code == 204
        assert not TimeEntry.objects.filter(pk=flagged.pk).exists()

    def test_reject_a_colleagues_is_refused(self, client, colleagues_flagged):
        assert client.post(self.reject_url(colleagues_flagged)).status_code == 403
        assert TimeEntry.objects.filter(pk=colleagues_flagged.pk).exists()

    def test_reject_leaves_an_approved_entry(self, client, entry):
        assert client.post(self.reject_url(entry)).status_code == 400
        assert TimeEntry.objects.filter(pk=entry.pk).exists()

    def test_edit_from_the_menu_saves_and_approves(self, client, flagged):
        assert client.get(self.edit_url(flagged)).context["approving"] is True
        response = client.post(
            self.edit_url(flagged), self.form_data(flagged, actions="Corrected")
        )
        assert response.status_code == 204
        flagged.refresh_from_db()
        assert flagged.actions == "Corrected"
        assert flagged.needs_approval is False

    def test_plain_edit_leaves_it_awaiting_approval(self, client, flagged):
        url = reverse("activity:time-edit", args=[flagged.id])
        assert client.get(url).context["approving"] is False
        response = client.post(url, self.form_data(flagged, actions="Corrected"))
        assert response.status_code == 204
        flagged.refresh_from_db()
        assert flagged.actions == "Corrected"
        assert flagged.needs_approval is True

    def test_a_colleague_editing_from_the_menu_url_does_not_approve(
        self, client, colleagues_flagged
    ):
        response = client.post(
            self.edit_url(colleagues_flagged), self.form_data(colleagues_flagged)
        )
        assert response.status_code == 204
        colleagues_flagged.refresh_from_db()
        assert colleagues_flagged.needs_approval is True
