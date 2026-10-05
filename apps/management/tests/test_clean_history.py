"""clean_history prunes django-q's failed task rows along with the change
history: the cluster never prunes them itself."""

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from django_q.models import Failure, Task

pytestmark = pytest.mark.django_db


def _task(days_ago, success):
    stopped = timezone.now() - timedelta(days=days_ago)
    return Task.objects.create(
        id=uuid.uuid4().hex,
        name=f"task-{days_ago}-{success}",
        func="apps.management.tests.test_clean_history._task",
        started=stopped - timedelta(seconds=1),
        stopped=stopped,
        success=success,
    )


def _run(*args):
    out = StringIO()
    call_command("clean_history", *args, stdout=out)
    return out.getvalue()


def test_old_failures_are_pruned_and_the_rest_kept():
    old_failure = _task(120, success=False)
    recent_failure = _task(10, success=False)
    old_success = _task(120, success=True)

    output = _run("--days", "90")

    assert not Failure.objects.filter(pk=old_failure.pk).exists()
    assert Failure.objects.filter(pk=recent_failure.pk).exists()
    assert Task.objects.filter(pk=old_success.pk).exists()
    assert "failed tasks: 1 records deleted" in output


def test_dry_run_counts_failures_without_deleting():
    old_failure = _task(120, success=False)

    output = _run("--days", "90", "--dry-run")

    assert Failure.objects.filter(pk=old_failure.pk).exists()
    assert "failed tasks: 1 records would be deleted" in output
