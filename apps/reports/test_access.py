"""Who can open Reports. The gate is the Reports permission, which is off
until an administrator turns it on; the staff flag plays no part."""

import pytest
from django.test import Client

from apps.accounts.models import CustomUser

pytestmark = pytest.mark.django_db

REPORT_PAGES = [
    "/reports/",
    "/reports/revenue/",
    "/reports/activity/",
    "/reports/realization/",
    "/reports/wip/",
    "/reports/intakes/",
    "/reports/clients/",
    "/reports/aging/",
]


def _client(**fields):
    user = CustomUser.objects.create(username="Rae", email="rae@example.com", **fields)
    user.set_password("clawboy")
    user.save()
    client = Client()
    client.login(username="Rae", password="clawboy")
    client.get("/dash/")
    return client


def test_a_new_user_does_not_have_the_reports_permission():
    assert CustomUser.objects.create(username="New").perm_reports is False


@pytest.mark.parametrize("path", REPORT_PAGES)
def test_reports_are_refused_without_the_permission(path):
    client = _client()

    assert client.get(path).status_code == 403


@pytest.mark.parametrize("path", REPORT_PAGES)
def test_reports_open_with_the_permission_and_no_staff_flag(path):
    client = _client(perm_reports=True)

    assert client.get(path, follow=True).status_code == 200


def test_an_administrator_needs_neither(db):
    client = _client(role="ADMIN")

    assert client.get("/reports/revenue/").status_code == 200


def test_the_staff_flag_alone_opens_nothing():
    client = _client(is_staff=True)

    assert client.get("/reports/revenue/").status_code == 403
