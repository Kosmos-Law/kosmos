"""One user's failed send does not cost the next user their digest."""

import pytest
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.tasks import digest
from apps.tasks.models import Task

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_digest_users(user):
    user.digest_enabled = True
    user.digest_include_weekends = True
    user.save()
    second = CustomUser.objects.create(
        username="Zara",
        email="zara@example.com",
        user_rate=100,
        digest_enabled=True,
        digest_include_weekends=True,
    )
    Task.objects.create(
        user=user,
        description="Something to report",
        status="Pending",
        date_due=timezone.localdate(),
    )
    return user, second


def test_a_failed_send_is_logged_and_the_loop_goes_on(
    two_digest_users, monkeypatch, caplog
):
    first, second = two_digest_users
    sent_to = []

    def send_mail(recipient_list, **kwargs):
        if recipient_list == [first.email]:
            raise ConnectionRefusedError("SMTP down")
        sent_to.append(recipient_list[0])

    monkeypatch.setattr(digest, "send_mail", send_mail)

    with caplog.at_level("ERROR", logger="apps.tasks.digest"):
        digest.send_daily_digest()

    assert sent_to == [second.email]
    assert any(
        str(first.pk) in record.getMessage()
        and "Daily digest failed" in record.getMessage()
        for record in caplog.records
    )
