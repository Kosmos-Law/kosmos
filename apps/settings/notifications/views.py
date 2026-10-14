import logging
import secrets
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import URLValidator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from apps.accounts.totp import qr_svg
from apps.intakes.access import can_see_intakes
from apps.tasks.digest import send_digest_for_user
from utils import notify
from utils.mail import email_delivers
from utils.toasts import toast_error

logger = logging.getLogger(__name__)


def _ntfy_subscribe_link(user):
    """The link that opens the ntfy app on a phone, subscribing it to the
    user's topic (ntfy://server/topic)."""
    server = urlsplit(user.ntfy_server)
    link = f"ntfy://{server.netloc}{server.path.rstrip('/')}/{notify.topic(user)}"
    if server.scheme == "http":
        link += "?secure=false"
    return link


def _notifications_context(request, **extra):
    user = request.user
    context = {
        "app": "settings",
        "subapp": "notifications",
        "ntfy_suffix": settings.NTFY_TOPIC_SUFFIX,
        "not_production": settings.NOT_PRODUCTION,
        "email_notifications": settings.EMAIL_NOTIFICATIONS,
        "test_result": request.GET.get("test"),
        "test_error": request.session.pop("ntfy_test_error", ""),
    }
    if user.ntfy_topic:
        link = _ntfy_subscribe_link(user)
        context |= {
            "ntfy_subscribe_link": link,
            # the link as a QR code too, for the phone's camera to read
            "ntfy_qr": mark_safe(qr_svg(link)),
            "ntfy_topic_here": notify.topic(user),
        }
    return context | extra


@login_required
def notifications_index(request):
    return render(
        request, "settings/notifications/index.html", _notifications_context(request)
    )


def _new_ntfy_topic():
    """A topic no one will guess: ntfy delivers a topic's messages to
    anyone who names it."""
    return "kosmos-" + secrets.token_urlsafe(24)


@login_required
@require_POST
def notify_by(request):
    """Choose the default channel for notifications: email or ntfy (push).
    Choosing ntfy the first time gives the user their topic."""
    user = request.user
    choice = request.POST.get("notify_by")
    if choice in dict(user.NOTIFY_CHOICES):
        user.notify_by = choice
        if choice == "ntfy" and not user.ntfy_topic:
            user.ntfy_topic = _new_ntfy_topic()
        user.save(update_fields=["notify_by", "ntfy_topic"])
    return redirect("settings:notifications-index")


def _save_ntfy(request):
    """Save the ntfy server and access token from the form. Returns an
    error message, or "" when saved."""
    user = request.user
    server = request.POST.get("ntfy_server", "").strip() or "https://ntfy.sh"
    try:
        URLValidator(schemes=["http", "https"])(server)
    except ValidationError:
        return "Enter the server's address, like https://ntfy.sh."
    user.ntfy_server = server.rstrip("/")
    user.ntfy_token = request.POST.get("ntfy_token", "").strip()
    user.save(update_fields=["ntfy_server", "ntfy_token"])
    return ""


@login_required
@require_POST
def ntfy_settings(request):
    error = _save_ntfy(request)
    if error:
        return render(
            request,
            "settings/notifications/index.html",
            _notifications_context(request, ntfy_error=error),
        )
    return redirect("settings:notifications-index")


@login_required
@require_POST
def ntfy_new_topic(request):
    """A topic for a user who has none yet, or a new one for a topic that
    has got out: the old one stops."""
    request.user.ntfy_topic = _new_ntfy_topic()
    request.user.save(update_fields=["ntfy_topic"])
    return redirect("settings:notifications-index")


@login_required
@require_POST
def ntfy_test(request):
    """Save the form as it stands, then push a test to the topic."""
    error = _save_ntfy(request)
    if error:
        return render(
            request,
            "settings/notifications/index.html",
            _notifications_context(request, ntfy_error=error),
        )
    result = notify.test_message(request.user)
    if not result["success"]:
        request.session["ntfy_test_error"] = result.get("error", "")
    return redirect(
        reverse("settings:notifications-index")
        + ("?test=sent" if result["success"] else "?test=failed")
    )


@login_required
def toggle_digest(request):
    user = request.user
    user.digest_enabled = not user.digest_enabled
    user.save(update_fields=["digest_enabled"])
    return render(request, "settings/notifications/preferences.html")


@login_required
def toggle_weekends(request):
    user = request.user
    user.digest_include_weekends = not user.digest_include_weekends
    user.save(update_fields=["digest_include_weekends"])
    return render(request, "settings/notifications/preferences.html")


@login_required
@require_POST
def toggle_new_intakes(request):
    user = request.user
    if not can_see_intakes(user):
        raise PermissionDenied
    user.notify_new_intakes = not user.notify_new_intakes
    user.save(update_fields=["notify_new_intakes"])
    return render(request, "settings/notifications/preferences.html")


@login_required
def send_test_digest(request):
    user = request.user
    if not user.email:
        return render(
            request,
            "settings/notifications/preferences.html",
            {"test_result": "error", "test_message": "No email address on file."},
        )

    # A mail server that refuses the message must not become a 500: the
    # panel swaps in place, so say what went wrong there and in a toast.
    try:
        sent = send_digest_for_user(user)
    except Exception as exc:
        logger.exception("Test digest send failed for user %s", user.pk)
        message = f"The test digest could not be sent: {exc}"
        response = render(
            request,
            "settings/notifications/preferences.html",
            {"test_result": "error", "test_message": message},
        )
        return toast_error(response, message)

    result = "success" if sent else "info"
    if not sent:
        message = "No events or tasks to include, so no email was sent."
    elif email_delivers():
        message = f"Test digest sent to {user.email}."
    else:
        result = "error"
        message = (
            "Email is not set up, so the test digest was logged on the server "
            "instead of sent."
        )

    return render(
        request,
        "settings/notifications/preferences.html",
        {"test_result": result, "test_message": message},
    )
