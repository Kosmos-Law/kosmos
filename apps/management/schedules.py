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


def schedule_specs(auto_summary_time="30 1"):
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
            "calendar-sync",
            "apps.calendar.sync.scheduled_sync",
            "*/2 * * * *",
            description=(
                "Two-way Google Calendar sync: pushes pending local changes "
                "and deletions, then pulls changes from Google. Does nothing "
                "until Google Calendar is connected."
            ),
        ),
        ScheduleSpec(
            "drive-sync",
            "apps.drive.google.scheduled_sync",
            "* * * * *",
            description=(
                "Incremental Google Drive sync of linked matter folders "
                "through the Drive Changes API. Does nothing until Google "
                "Drive is connected."
            ),
        ),
        ScheduleSpec(
            "drive-sync-nightly-full",
            "apps.drive.google.scheduled_sync_full",
            "30 3 * * *",
            description=(
                "Full re-crawl of every linked Drive folder, to catch "
                "anything the incremental sync missed."
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
            "auto-summary-nightly",
            "apps.case.ai.auto_summary.scheduled_refresh_auto_summaries",
            f"{auto_summary_time} * * 0,2-6",
            description=(
                "Queues an incremental refresh of the AI Auto Summary (and "
                "then the Auto Agenda) for every open matter. Runs only when "
                "ENV=prod."
            ),
        ),
        ScheduleSpec(
            "auto-summary-weekly-rebuild",
            "apps.case.ai.auto_summary.scheduled_refresh_auto_summaries_full",
            f"{auto_summary_time} * * 1",
            description=(
                "Rebuilds every open matter's AI Auto Summary from the full "
                "record, so summaries do not drift by compounding on earlier "
                "summaries. Runs only when ENV=prod."
            ),
        ),
        ScheduleSpec(
            "auto-daily-plan",
            "apps.dash.agenda.scheduled_refresh_daily_plans",
            "45 2 * * *",
            description=(
                "Queues the AI daily plan for every active user, after the "
                "night's matter summaries have refreshed. Runs only when "
                "ENV=prod."
            ),
        ),
        ScheduleSpec(
            "chat-purge-weekly",
            "apps.case.ai.purge.scheduled_purge_closed_chats",
            "0 3 * * 0",
            description=(
                "Deletes AI chat history for matters that have been closed "
                "for longer than CHAT_RETENTION_DAYS (180 by default; 0 keeps "
                "chats indefinitely)."
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


def install_schedules(names=None, auto_summary_time="30 1"):
    """Create or update selected schedules and return ``(spec, created)`` pairs."""
    wanted = set(names) if names is not None else None
    local_now = timezone.localtime(timezone.now())
    results = []

    for spec in schedule_specs(auto_summary_time=auto_summary_time):
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
