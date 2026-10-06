from datetime import timedelta

from django.core.cache import cache
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_safe

# A running worker moves each schedule's next run into the future within
# seconds of it coming due, and the shortest schedules run every minute. A
# schedule still overdue after this long means nothing is processing them.
WORKER_STALE_AFTER = timedelta(minutes=5)

WORKER_STATUS_CACHE_KEY = "worker_health_running"
WORKER_STATUS_CACHE_SECONDS = 60


def _response(status, http_status=200):
    response = JsonResponse({"status": status}, status=http_status)
    response["Cache-Control"] = "no-store"

    return response


@require_safe
def live(request):
    return _response("ok")


@require_safe
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return _response("unavailable", http_status=503)

    return _response("ok")


def worker_is_running():
    """Is the background worker processing its schedules?

    The web application answers /health/ready/ whether or not qcluster is
    running, so a stopped worker is otherwise silent: documents stop being
    processed and syncs stop, with nothing to alert on. The worker has no
    port to probe, but its effect is visible in the database: it keeps every
    schedule's next run in the future.
    """
    from django_q.models import Schedule

    try:
        schedules = Schedule.objects.exclude(repeats=0)
        if not schedules.exists():
            # setup_schedules has not been run; nothing shows the worker alive.
            return False
        overdue = schedules.filter(
            next_run__lt=timezone.now() - WORKER_STALE_AFTER
        ).exists()
    except DatabaseError:
        return False

    return not overdue


def worker_looks_down():
    """worker_is_running(), inverted and cached briefly for page renders.

    The admin notice and the OCR badge ask on every render and every poll,
    so the answer is held for WORKER_STATUS_CACHE_SECONDS in the default
    (per-process) cache. Each gunicorn worker keeps its own copy, which is
    fine for a read-only health check: at worst one process notices a
    minute later than another.
    """
    running = cache.get(WORKER_STATUS_CACHE_KEY)
    if running is None:
        running = worker_is_running()
        cache.set(WORKER_STATUS_CACHE_KEY, running, WORKER_STATUS_CACHE_SECONDS)
    return not running


@require_safe
def worker(request):
    """JSON health check for the background worker (see worker_is_running)."""
    if worker_is_running():
        return _response("ok")
    return _response("unavailable", http_status=503)
