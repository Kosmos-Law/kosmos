"""Email firm users who asked to hear about new intakes.

A user turns this on under Settings > Notifications. Whoever added the
intake is left out (they already know), and so is anyone without the
Intakes permission. Every failure is logged and swallowed: a mail server
refusing a message must never cost the intake itself.
"""

import logging

from django.core.mail import send_mail
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.intakes.access import can_see_intakes
from utils.links import absolute

logger = logging.getLogger(__name__)


def intake_recipients(creator=None):
    """Active users who want new-intake emails and may see intakes, minus
    the creator."""
    users = CustomUser.objects.filter(is_active=True, notify_new_intakes=True).exclude(
        Q(email="") | Q(email__isnull=True)
    )
    if creator is not None:
        users = users.exclude(pk=creator.pk)
    return [user for user in users if can_see_intakes(user)]


def notify_new_intake(intake, creator=None, request=None):
    """Send each recipient one email about a newly created intake. Returns
    the number sent."""
    try:
        recipients = intake_recipients(creator)
    except Exception:
        logger.exception("New-intake recipients failed for intake %s", intake.pk)
        return 0
    if not recipients:
        return 0

    context = {
        "intake": intake,
        "creator": creator,
        "url": absolute(reverse("intakes:detail-index", args=[intake.pk]), request),
    }
    message = render_to_string("emails/new_intake.txt", context)
    subject = f"New intake: {intake.name}"

    sent = 0
    for user in recipients:
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=[user.email],
            )
            sent += 1
        except Exception:
            logger.exception(
                "New-intake email failed for user %s, intake %s", user.pk, intake.pk
            )
    return sent
