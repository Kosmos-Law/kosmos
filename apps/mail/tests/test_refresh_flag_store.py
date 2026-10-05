"""The Emails tab's "refresh running" flag lives in the cross-process
ai_status cache, not the per-worker default cache: a status poll served by
another gunicorn worker must still see the sync in flight."""

import pytest
from django.core.cache import cache, caches
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_sync_thread(monkeypatch):
    # The flag is what is under test; the resync itself never runs.
    class Thread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr("apps.mail.views.threading.Thread", Thread)


@pytest.fixture(autouse=True)
def clear_flag(matter):
    key = f"emails_refresh_{matter.id}"
    caches["ai_status"].delete(key)
    cache.delete(key)
    yield
    caches["ai_status"].delete(key)
    cache.delete(key)


def test_refresh_sets_the_flag_in_the_cross_process_store(client, matter, fake_gmail):
    client.post(reverse("case:emails-refresh", args=[matter.id]))

    assert caches["ai_status"].get(f"emails_refresh_{matter.id}") == "running"
    assert cache.get(f"emails_refresh_{matter.id}") is None


def test_poll_from_another_worker_sees_the_running_flag(client, matter, fake_gmail):
    # Another worker set the flag: only the shared store carries it.
    caches["ai_status"].set(f"emails_refresh_{matter.id}", "running", 600)

    response = client.get(
        reverse("case:emails-refresh-status", args=[matter.id]), {"polls": 1}
    )

    body = response.content.decode()
    assert "Syncing" in body
    assert "HX-Trigger" not in response


def test_poll_ignores_a_flag_in_the_per_process_cache(client, matter, fake_gmail):
    cache.set(f"emails_refresh_{matter.id}", "running", 600)

    response = client.get(
        reverse("case:emails-refresh-status", args=[matter.id]), {"polls": 1}
    )

    assert response["HX-Trigger"] == "emailsChanged"
