"""Canonical Django-Q schedules for the application.

Keeping schedule definitions in one module gives every environment the same
idempotent setup path while preserving the small legacy setup commands as
backwards-compatible aliases.
"""

from dataclasses import dataclass

from croniter import croniter
from django.utils import timezone
from django_q.models import Schedule


@dataclass(frozen=True)
class ScheduleSpec:
    name: str
    func: str
    cron: str
    # One sentence for operators. scripts/gen_docs_reference.py copies it
    # into docs/reference/schedules.md, so keep it accurate when the job
    # changes.
    description: str = ""


def schedule_specs():
    return (
        ScheduleSpec(
            "daily-digest",
            "apps.tasks.digest.send_daily_digest",
            "0 7 * * *",
            description=(
                "Emails each active user who has the digest switched on a "
                "summary of overdue, today's and upcoming items."
            ),
        ),
        ScheduleSpec(
            "event-reminders",
            "apps.calendar.reminders.send_due",
            "* * * * *",
            description=(
                "Sends the event notifications that have come due, by email "
                "or pushed to the ntfy app, as each one says."
            ),
        ),
        ScheduleSpec(
            "google-contacts-auto",
            "apps.contacts.google.scheduled_sync_automatic",
            "*/15 * * * *",
            description=(
                "Copies the clients (or Client groups) of open matters to the "
                "Google Contacts of each user who chose automatic copies, and "
                "removes the ones it added once their matter is no longer open."
            ),
        ),
        ScheduleSpec(
            "gmail-sync",
            "apps.mail.google.scheduled_sync",
            "*/2 * * * *",
            description=(
                "Syncs labelled Gmail messages onto their mapped matters, "
                "across every connected mailbox. Does nothing until a mailbox "
                "is connected and a label is linked to a matter."
            ),
        ),
        ScheduleSpec(
            "gmail-sync-weekly-full",
            "apps.mail.google.scheduled_sync_full",
            "15 3 * * 1",
            description="Full Gmail re-sync of every linked label.",
        ),
        ScheduleSpec(
            "chat-purge-weekly",
            "apps.ai.purge.scheduled_purge_closed_chats",
            "0 3 * * 0",
            description=(
                "Deletes AI chat history for matters that have been closed "
                "for longer than CHAT_RETENTION_DAYS (180 by default; 0 keeps "
                "chats indefinitely)."
            ),
        ),
        ScheduleSpec(
            "quickbooks-sync",
            "apps.books.sync.scheduled_sync",
            "*/30 * * * *",
            description=(
                "Mirrors the firm's QuickBooks Online company into Books: the "
                "chart of accounts, every transaction, and a check against "
                "QuickBooks's own trial balance. Does nothing until QuickBooks "
                "is connected under Settings > Integrations."
            ),
        ),
        ScheduleSpec(
            "payments-reconcile",
            "apps.invoicing.pay.reconcile.poll_pending",
            "15 * * * *",
            description=(
                "Asks the payment processor for the current state of every "
                "online payment and trust deposit still in flight, and "
                "settles, confirms or reverses it. The backstop for a webhook "
                "that never arrived."
            ),
        ),
    )


def install_schedules(names=None):
    """Create or update selected schedules and return ``(spec, created)`` pairs."""
    wanted = set(names) if names is not None else None
    local_now = timezone.localtime(timezone.now())
    results = []

    for spec in schedule_specs():
        if wanted is not None and spec.name not in wanted:
            continue
        _, created = Schedule.objects.update_or_create(
            name=spec.name,
            defaults={
                "func": spec.func,
                "schedule_type": Schedule.CRON,
                "cron": spec.cron,
                "repeats": -1,
                # Prevent a newly-created or changed schedule from firing as
                # soon as qcluster starts; wait for its next real cron slot.
                "next_run": croniter(spec.cron, local_now).get_next(type(local_now)),
            },
        )
        results.append((spec, created))

    return results
