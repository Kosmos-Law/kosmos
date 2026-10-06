from unittest.mock import patch

import pytest
from django.db import OperationalError
from django.urls import reverse


def test_liveness_does_not_require_authentication_or_database(client):
    with patch("config.health.connection.cursor") as cursor:
        response = client.get(reverse("health-live"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response["Cache-Control"] == "no-store"
    cursor.assert_not_called()


@pytest.mark.django_db
def test_readiness_checks_database(client):
    response = client.get(reverse("health-ready"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_503_when_database_is_unavailable(client):
    with patch("config.health.connection.cursor", side_effect=OperationalError):
        response = client.get(reverse("health-ready"))

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.django_db
def test_worker_is_healthy_while_schedules_are_kept_current(client):
    from django.core.management import call_command

    call_command("setup_schedules", verbosity=0)

    response = client.get(reverse("health-worker"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_worker_is_unavailable_once_a_schedule_is_left_overdue(client):
    """A running worker moves a due schedule on within seconds. One left
    overdue for minutes means nothing is processing them."""
    from datetime import timedelta

    from django.core.management import call_command
    from django.utils import timezone
    from django_q.models import Schedule

    call_command("setup_schedules", verbosity=0)
    Schedule.objects.filter(name="drive-sync").update(
        next_run=timezone.now() - timedelta(minutes=30)
    )

    response = client.get(reverse("health-worker"))

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.django_db
def test_worker_is_unavailable_when_no_schedules_are_installed(client):
    response = client.get(reverse("health-worker"))

    assert response.status_code == 503


# The same check, cached, drives the admin notice in base.html.

WORKER_NOTICE = "background worker isn"


@pytest.fixture
def clear_worker_cache():
    from django.core.cache import cache

    from config.health import WORKER_STATUS_CACHE_KEY

    cache.delete(WORKER_STATUS_CACHE_KEY)
    yield
    cache.delete(WORKER_STATUS_CACHE_KEY)


@pytest.mark.django_db
def test_worker_looks_down_is_cached(clear_worker_cache):
    from django.core.management import call_command

    from config.health import worker_looks_down

    assert worker_looks_down()  # no schedules installed
    call_command("setup_schedules", verbosity=0)
    # Still the cached answer until it expires.
    assert worker_looks_down()


def _page_for(role):
    from django.test import Client

    from apps.accounts.models import CustomUser

    user = CustomUser.objects.create(
        username=f"u-{role}", email=f"{role}@example.com", role=role
    )
    client = Client()
    client.force_login(user)
    client.get("/dash/")  # daily dash session, so later pages don't redirect
    return client.get(reverse("tasks-index")).content.decode()


@pytest.mark.django_db
def test_admins_see_a_notice_while_the_worker_is_down(clear_worker_cache):
    assert WORKER_NOTICE in _page_for("ADMIN")


@pytest.mark.django_db
def test_other_users_never_see_the_worker_notice(clear_worker_cache):
    assert WORKER_NOTICE not in _page_for("USER")


@pytest.mark.django_db
def test_no_notice_while_the_worker_runs(clear_worker_cache):
    from django.core.management import call_command

    call_command("setup_schedules", verbosity=0)
    assert WORKER_NOTICE not in _page_for("ADMIN")
