"""The Notifications section of the Edit Event dialog: the user's own
notifications on the event, and the row that adds one. A firm's event may
be on several people's calendars, so each user sees and changes only the
notifications they added."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.calendar.access import event_for_user
from apps.calendar.reminder_forms import ReminderForm


def reminders_context(event, user, form=None):
    """The section's context (templates/components/reminders.html): the
    user's notifications on the event, each with its delete address, and
    the form that adds one."""
    reminders = list(event.reminders.filter(user=user))
    for reminder in reminders:
        reminder.delete_url = reverse(
            "calendar:reminder-delete", args=[event.id, reminder.id]
        )
    return {
        "event": event,
        "reminders": reminders,
        "reminder_form": form or ReminderForm(event=event, user=user),
        "reminder_add_url": reverse("calendar:reminder-add", args=[event.id]),
    }


@login_required
@require_POST
def reminder_add(request, id):
    """Add a notification to the event and re-render the section."""
    event = event_for_user(id, request.user)
    form = ReminderForm(request.POST, event=event, user=request.user)
    if form.is_valid():
        reminder = form.save(commit=False)
        reminder.event = event
        reminder.user = request.user
        reminder.save()
        form = None
    return render(
        request,
        "components/reminders.html",
        reminders_context(event, request.user, form),
    )


@login_required
@require_http_methods(["POST", "DELETE"])
def reminder_delete(request, id, reminder_id):
    """Remove one of the user's notifications from the event and re-render
    the section."""
    event = event_for_user(id, request.user)
    event.reminders.filter(user=request.user, pk=reminder_id).delete()
    return render(
        request, "components/reminders.html", reminders_context(event, request.user)
    )
