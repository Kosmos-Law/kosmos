"""Event notifications: when they go out, how they read, how they are
added and removed on the edit form, and what the scheduled job sends."""

from datetime import date, datetime, time, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.calendar import reminders
from apps.calendar.models import Event, EventReminder

pytestmark = pytest.mark.django_db


def _aware(*args):
    return timezone.make_aware(datetime(*args))


@pytest.fixture(autouse=True)
def _email_on(settings):
    settings.EMAIL_NOTIFICATIONS = True


@pytest.fixture
def timed(user, matter):
    return Event.objects.create(
        user=user,
        matter=matter,
        date=date(2030, 3, 4),
        start_time=time(14, 0),
        end_time=time(15, 0),
        description="Deposition",
        location="100 Main St",
        status="Pending",
    )


@pytest.fixture
def all_day(user):
    return Event.objects.create(
        user=user, date=date(2030, 3, 4), description="Trial", status="Pending"
    )


@pytest.fixture
def other_user():
    return CustomUser.objects.create(username="Other", email="other@example.com")


# --- when and how it reads -------------------------------------------------


@pytest.mark.parametrize(
    "amount, unit, fire_at, words",
    [
        (30, "minutes", _aware(2030, 3, 4, 13, 30), "30 minutes before"),
        (1, "hours", _aware(2030, 3, 4, 13, 0), "1 hour before"),
        (2, "days", _aware(2030, 3, 2, 14, 0), "2 days before"),
        (1, "weeks", _aware(2030, 2, 25, 14, 0), "1 week before"),
        (0, "minutes", _aware(2030, 3, 4, 14, 0), "At the start"),
    ],
)
def test_a_timed_event_counts_back_from_its_start(
    timed, user, amount, unit, fire_at, words
):
    reminder = EventReminder(event=timed, user=user, amount=amount, unit=unit)

    assert reminder.fire_at == fire_at
    assert reminder.describe() == words


@pytest.mark.parametrize(
    "amount, unit, at, fire_at, words",
    [
        (1, "days", time(9, 0), _aware(2030, 3, 3, 9, 0), "1 day before at 9:00 AM"),
        (0, "days", time(7, 30), _aware(2030, 3, 4, 7, 30), "That day at 7:30 AM"),
        (1, "weeks", None, _aware(2030, 2, 25, 9, 0), "1 week before at 9:00 AM"),
    ],
)
def test_an_all_day_event_goes_out_at_a_time_of_day(
    all_day, user, amount, unit, at, fire_at, words
):
    reminder = EventReminder(
        event=all_day, user=user, amount=amount, unit=unit, time=at
    )

    assert reminder.fire_at == fire_at
    assert reminder.describe() == words


def test_an_event_with_no_date_has_no_time_to_fire(user):
    event = Event.objects.create(user=user, date=None, description="Undated")

    assert EventReminder(event=event, user=user, amount=1, unit="days").fire_at is None


# --- the edit form ---------------------------------------------------------


def test_the_edit_form_lists_notifications_and_offers_to_add_one(client, user, timed):
    EventReminder.objects.create(event=timed, user=user, amount=30, unit="minutes")

    html = client.get(reverse("calendar:edit", args=[timed.id])).content.decode()

    assert "30 minutes before" in html
    assert reverse("calendar:reminder-add", args=[timed.id]) in html
    assert 'name="time"' not in html


def test_an_all_day_events_form_offers_days_weeks_and_a_time(client, all_day):
    html = client.get(reverse("calendar:edit", args=[all_day.id])).content.decode()

    assert 'name="time"' in html
    assert 'value="days"' in html
    assert 'value="minutes"' not in html


def test_the_add_form_has_no_notifications_section(client):
    html = client.get(reverse("calendar:add")).content.decode()

    assert 'id="reminders"' not in html


def test_push_is_offered_only_once_the_phone_is_set_up(client, user, timed):
    html = client.get(reverse("calendar:edit", args=[timed.id])).content.decode()
    assert 'value="ntfy"' not in html

    # (an update, not a save: the fixture's user is stale once the client
    # has opened the dash, and saving it would undo that)
    CustomUser.objects.filter(pk=user.pk).update(ntfy_topic="kosmos-secret")
    html = client.get(reverse("calendar:edit", args=[timed.id])).content.decode()
    assert 'value="ntfy"' in html


def test_adding_a_notification(client, user, timed):
    response = client.post(
        reverse("calendar:reminder-add", args=[timed.id]),
        {"amount": 2, "unit": "hours"},
    )

    assert response.status_code == 200
    assert "2 hours before" in response.content.decode()
    reminder = timed.reminders.get()
    assert (reminder.amount, reminder.unit, reminder.time) == (2, "hours", None)
    assert reminder.user == user
    assert reminder.channel == "email"


def test_a_notification_takes_the_users_default_channel(client, user, timed):
    CustomUser.objects.filter(pk=user.pk).update(
        notify_by="ntfy", ntfy_topic="kosmos-secret"
    )

    client.post(
        reverse("calendar:reminder-add", args=[timed.id]),
        {"amount": 2, "unit": "hours"},
    )

    assert timed.reminders.get().channel == "ntfy"


def test_adding_to_an_all_day_event_keeps_the_time(client, all_day):
    client.post(
        reverse("calendar:reminder-add", args=[all_day.id]),
        {"amount": 1, "unit": "days", "time": "08:00"},
    )

    assert all_day.reminders.get().time == time(8, 0)


def test_an_all_day_event_refuses_minutes(client, all_day):
    response = client.post(
        reverse("calendar:reminder-add", args=[all_day.id]),
        {"amount": 30, "unit": "minutes"},
    )

    assert response.status_code == 200
    assert "days or weeks" in response.content.decode()
    assert not all_day.reminders.exists()


def test_removing_a_notification(client, user, timed):
    reminder = EventReminder.objects.create(
        event=timed, user=user, amount=30, unit="minutes"
    )

    response = client.post(
        reverse("calendar:reminder-delete", args=[timed.id, reminder.id])
    )

    assert response.status_code == 200
    assert "No notifications" in response.content.decode()
    assert not timed.reminders.exists()


def test_each_user_sees_and_removes_only_their_own(client, user, other_user, timed):
    """A firm's event may be on several people's calendars: another user's
    notification is neither listed nor removable."""
    theirs = EventReminder.objects.create(
        event=timed, user=other_user, amount=1, unit="days"
    )
    EventReminder.objects.create(event=timed, user=user, amount=30, unit="minutes")

    html = client.get(reverse("calendar:edit", args=[timed.id])).content.decode()
    assert "30 minutes before" in html
    assert "1 day before" not in html

    client.post(reverse("calendar:reminder-delete", args=[timed.id, theirs.id]))
    assert EventReminder.objects.filter(pk=theirs.pk).exists()


def test_an_event_the_user_cannot_see_takes_no_notification(user, other_user):
    """An event on a matter the user is not assigned to is refused."""
    from apps.matters.models import Matter, PracticeArea

    area = PracticeArea.objects.create(name="Private", is_active=True)
    matter = Matter.objects.create(
        name="Closed Door", status="Open", practice_area=area
    )
    event = Event.objects.create(
        user=other_user, matter=matter, date=date(2030, 3, 4), description="Hearing"
    )
    CustomUser.objects.filter(pk=user.pk).update(perm_all_matters=False)
    user.refresh_from_db()
    client = Client()
    client.force_login(user)
    client.get("/dash/")

    response = client.post(
        reverse("calendar:reminder-add", args=[event.id]),
        {"amount": 1, "unit": "days"},
    )

    assert response.status_code == 403
    assert not event.reminders.exists()


def test_deleting_the_event_removes_its_notifications(client, user, timed):
    EventReminder.objects.create(event=timed, user=user, amount=30, unit="minutes")

    client.delete(reverse("calendar:delete", args=[timed.id]))

    assert not EventReminder.objects.exists()


# --- sending ---------------------------------------------------------------


def test_a_due_notification_is_sent_once(user, timed, mailoutbox):
    reminder = EventReminder.objects.create(
        event=timed, user=user, amount=30, unit="minutes"
    )
    due = _aware(2030, 3, 4, 13, 31)

    assert reminders.send_due(now=due) == (1, 0)
    assert mailoutbox[0].subject == "Deposition - Monday, March 4 at 2:00 PM – 3:00 PM"
    assert mailoutbox[0].to == ["testuser@example.com"]
    assert "Matter: Sample Test Matter" in mailoutbox[0].body
    assert "Location: 100 Main St" in mailoutbox[0].body
    reminder.refresh_from_db()
    assert reminder.sent_for == _aware(2030, 3, 4, 13, 30)

    assert reminders.send_due(now=due + timedelta(minutes=5)) == (0, 0)
    assert len(mailoutbox) == 1


def test_a_notification_not_yet_due_waits(user, timed, mailoutbox):
    EventReminder.objects.create(event=timed, user=user, amount=30, unit="minutes")

    assert reminders.send_due(now=_aware(2030, 3, 4, 13, 0)) == (0, 0)
    assert mailoutbox == []


def test_a_notification_long_past_is_let_go(user, timed, mailoutbox):
    reminder = EventReminder.objects.create(
        event=timed, user=user, amount=30, unit="minutes"
    )

    assert reminders.send_due(now=_aware(2030, 3, 4, 18, 0)) == (0, 0)
    assert mailoutbox == []
    reminder.refresh_from_db()
    assert reminder.sent_for == _aware(2030, 3, 4, 13, 30)


def test_a_moved_event_is_notified_again(user, timed, mailoutbox):
    EventReminder.objects.create(event=timed, user=user, amount=30, unit="minutes")
    reminders.send_due(now=_aware(2030, 3, 4, 13, 31))

    timed.date = date(2030, 3, 5)
    timed.save()

    assert reminders.send_due(now=_aware(2030, 3, 5, 13, 31)) == (1, 0)
    assert len(mailoutbox) == 2
    assert "Tuesday, March 5" in mailoutbox[1].subject


def test_an_all_day_event_over_several_days_says_so(user, all_day, mailoutbox):
    all_day.end_date = date(2030, 3, 6)
    all_day.save()
    EventReminder.objects.create(
        event=all_day, user=user, amount=1, unit="days", time=time(9, 0)
    )

    assert reminders.send_due(now=_aware(2030, 3, 3, 9, 1)) == (1, 0)
    assert mailoutbox[0].subject == "Trial - Monday, March 4"
    assert "Through: Wednesday, March 6" in mailoutbox[0].body


def test_a_deactivated_users_notifications_are_not_sent(user, timed, mailoutbox):
    EventReminder.objects.create(event=timed, user=user, amount=30, unit="minutes")
    CustomUser.objects.filter(pk=user.pk).update(is_active=False)

    assert reminders.send_due(now=_aware(2030, 3, 4, 13, 31)) == (0, 0)
    assert mailoutbox == []


def test_email_off_counts_as_handled(settings, user, timed, mailoutbox):
    """Off production, nothing is emailed, and the notification is not
    tried again every minute."""
    settings.EMAIL_NOTIFICATIONS = False
    reminder = EventReminder.objects.create(
        event=timed, user=user, amount=30, unit="minutes"
    )

    assert reminders.send_due(now=_aware(2030, 3, 4, 13, 31)) == (1, 0)
    assert mailoutbox == []
    reminder.refresh_from_db()
    assert reminder.sent_for == _aware(2030, 3, 4, 13, 30)


def test_the_command_reports_what_it_sent(user, timed, mailoutbox, capsys):
    from django.core.management import call_command

    EventReminder.objects.create(event=timed, user=user, amount=0, unit="minutes")
    # Due now: the event is moved to start a minute ago
    now = timezone.localtime()
    timed.date = now.date()
    timed.start_time = (now - timedelta(minutes=1)).time().replace(second=0)
    timed.end_time = None
    timed.save()

    call_command("send_event_reminders")

    assert "Sent 1 notification(s), 0 error(s)" in capsys.readouterr().out
