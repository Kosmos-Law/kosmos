"""The Django admin is not installed. Every change to a record goes through
the application's own screens or the command line, where its rules apply."""

import pytest
from django.apps import apps
from django.test import Client

pytestmark = pytest.mark.django_db


def test_the_admin_app_is_not_installed():
    assert not apps.is_installed("django.contrib.admin")


@pytest.mark.parametrize("path", ["/admin/", "/admin/login/", "/admin/accounts/"])
def test_admin_addresses_do_not_exist(path):
    assert Client().get(path).status_code == 404
