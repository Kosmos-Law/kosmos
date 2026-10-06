import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.tasks.digest import send_digest_for_user
from utils.mail import email_delivers
from utils.toasts import toast_error

logger = logging.getLogger(__name__)


@login_required
def notifications_index(request):
    context = {
        "app": "settings",
        "subapp": "notifications",
    }
    return render(request, "settings/notifications/index.html", context)


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
