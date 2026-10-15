"""The Guests section of the Edit Event dialog: the people outside the
firm invited to the event, how each answered, and the row that invites
another (apps.calendar.invitations sends the email)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.calendar import invitations
from apps.calendar.access import event_for_user
from apps.calendar.guest_forms import GuestForm


def guests_context(event, form=None):
    """The section's context (templates/components/guests.html): the
    guests, each with its delete address, and the form that invites one,
    or None while the server has no calendar address to invite from."""
    guests = list(event.guests.all())
    for guest in guests:
        guest.delete_url = reverse("calendar:guest-delete", args=[event.id, guest.id])
    return {
        "event": event,
        "guests": guests,
        "guest_form": (form or GuestForm(event=event))
        if invitations.can_invite()
        else None,
        "guest_add_url": reverse("calendar:guest-add", args=[event.id]),
    }


@login_required
@require_POST
def guest_add(request, id):
    """Invite a guest to the event: the invitation goes out at once, and
    the section is re-rendered with them on it."""
    event = event_for_user(id, request.user)
    form = GuestForm(request.POST, event=event)
    if invitations.can_invite() and form.is_valid():
        guest = form.save(commit=False)
        guest.event = event
        guest.invited_by = request.user
        guest.save()
        if invitations.send_invitation(event, [guest], request.user):
            form = None
        else:
            # Not invited after all: the guest goes, and the user can try
            # again once the mail server answers
            guest.delete()
            form.add_error(
                None,
                "The invitation could not be emailed, so they were not added. "
                "Try again in a little while.",
            )
    return render(request, "components/guests.html", guests_context(event, form))


@login_required
@require_http_methods(["POST", "DELETE"])
def guest_delete(request, id, guest_id):
    """Take a guest off the event, telling them the invitation is
    cancelled."""
    event = event_for_user(id, request.user)
    guest = event.guests.filter(pk=guest_id).first()
    if guest is not None:
        invitations.send_cancellation(event, [guest], request.user)
        guest.delete()
    return render(request, "components/guests.html", guests_context(event))
