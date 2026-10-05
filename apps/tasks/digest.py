import logging
from datetime import timedelta

from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.calendar.access import events_for_user
from apps.calendar.models import Event
from apps.tasks.access import tasks_for_user
from apps.tasks.constants import ACTIVE_STATUSES
from apps.tasks.models import Task

logger = logging.getLogger(__name__)

LOOKAHEAD_DAYS = 3


def send_daily_digest():
    """Entry point called by Django-Q2 schedule.

    Queries all active users with digest_enabled=True and sends each
    a digest email summarising overdue, today, and upcoming items.
    """
    today = timezone.localdate()
    is_weekend = today.weekday() >= 5

    users = CustomUser.objects.filter(
        is_active=True,
        digest_enabled=True,
    ).exclude(Q(email="") | Q(email__isnull=True))

    for user in users:
        if is_weekend and not user.digest_include_weekends:
            continue
        # One address that bounces at the mail server must not cost the
        # rest of the firm their digest.
        try:
            send_digest_for_user(user)
        except Exception:
            logger.exception("Daily digest failed for user %s", user.pk)


def send_digest_for_user(user):
    """Build and send a single digest email for the given user.

    Returns True if an email was sent, False if there was nothing to report.
    A user limited to assigned matters sees the items on those matters and
    the items on no matter, as on the Dash. An admin sees everything.
    """
    today = timezone.localdate()
    upcoming_end = today + timedelta(days=LOOKAHEAD_DAYS)

    # Events
    events_qs = events_for_user(Event.objects.select_related("matter"), user)

    overdue_events = events_qs.filter(
        date__lt=today,
        status="Pending",
    ).order_by("date", "start_time")

    today_events = events_qs.filter(
        date=today,
        status="Pending",
    ).order_by("start_time")

    upcoming_events = events_qs.filter(
        date__gt=today,
        date__lte=upcoming_end,
        status="Pending",
    ).order_by("date", "start_time")

    # Tasks
    tasks_qs = tasks_for_user(Task.objects.select_related("user", "matter"), user)

    overdue_tasks = tasks_qs.filter(
        date_due__lt=today,
        status__in=ACTIVE_STATUSES,
    ).order_by("date_due", "-importance")

    today_tasks = tasks_qs.filter(
        date_due=today,
        status__in=ACTIVE_STATUSES,
    ).order_by("-importance")

    upcoming_tasks = tasks_qs.filter(
        date_due__gt=today,
        date_due__lte=upcoming_end,
        status__in=ACTIVE_STATUSES,
    ).order_by("date_due", "-importance")

    has_content = (
        overdue_events.exists()
        or overdue_tasks.exists()
        or today_events.exists()
        or today_tasks.exists()
        or upcoming_events.exists()
        or upcoming_tasks.exists()
    )

    if not has_content:
        return False

    context = {
        "user": user,
        "today": today,
        "overdue_events": overdue_events,
        "overdue_tasks": overdue_tasks,
        "today_events": today_events,
        "today_tasks": today_tasks,
        "upcoming_events": upcoming_events,
        "upcoming_tasks": upcoming_tasks,
        "lookahead_days": LOOKAHEAD_DAYS,
    }

    html_message = render_to_string("emails/daily_digest.html", context)
    text_message = render_to_string("emails/daily_digest.txt", context)

    send_mail(
        subject=f"Kosmos Daily Digest for {today.strftime('%A, %B %-d')}",
        message=text_message,
        from_email=None,
        recipient_list=[user.email],
        html_message=html_message,
    )

    return True
