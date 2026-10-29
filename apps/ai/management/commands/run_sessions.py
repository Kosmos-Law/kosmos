"""The sessions service: runs Claude Code turns off the web workers.

Polls for pending assistant messages and runs each on a thread
(``runtime.run_turn``), ``SESSIONS_CONCURRENCY`` at a time. A heartbeat
in the status cache tells the session page the service is up. Turns
left running by a previous process (a restart mid-turn) are marked
failed at start, since their harness process died with it.
"""

import logging
import signal
import threading
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections
from django.utils import timezone

from apps.ai.models import SessionMessage
from apps.ai.runtime import run_turn, service_heartbeat

logger = logging.getLogger(__name__)

POLL_SECONDS = 1.0
HEARTBEAT_SECONDS = 20.0


def run_turn_on_thread(message_id):
    """One turn on a pool thread, with the thread's connections closed
    after it so the pool never holds stale ones."""
    try:
        run_turn(message_id)
    finally:
        connections.close_all()


class Command(BaseCommand):
    help = "Run Claude Code session turns as they are requested."

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            force=True,
        )
        stop = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: stop.set())

        interrupted = SessionMessage.objects.filter(role="assistant", status="running")
        n = interrupted.update(
            status="failed",
            error="The sessions service restarted during this turn.",
            finished_at=timezone.now(),
        )
        if n:
            logger.warning("Marked %d turn(s) interrupted by the restart", n)

        concurrency = settings.SESSIONS_CONCURRENCY
        pool = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="turn")
        running = {}
        last_beat = 0.0
        logger.info("Sessions service up: %d turn(s) at a time", concurrency)
        try:
            while not stop.is_set():
                now = timezone.now().timestamp()
                if now - last_beat > HEARTBEAT_SECONDS:
                    service_heartbeat()
                    last_beat = now
                for message_id, future in list(running.items()):
                    if future.done():
                        del running[message_id]
                free = concurrency - len(running)
                if free > 0:
                    pending = list(
                        SessionMessage.objects.filter(
                            role="assistant", status="pending"
                        )
                        .exclude(id__in=list(running))
                        .order_by("id")
                        .values_list("id", flat=True)[:free]
                    )
                    for message_id in pending:
                        logger.info("Turn %s starting", message_id)
                        running[message_id] = pool.submit(
                            run_turn_on_thread, message_id
                        )
                close_old_connections()
                stop.wait(POLL_SECONDS)
        finally:
            logger.info(
                "Sessions service stopping; waiting for %d turn(s)", len(running)
            )
            pool.shutdown(wait=True)
