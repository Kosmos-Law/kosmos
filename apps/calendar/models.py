from datetime import datetime

from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.matters.models import Matter
from utils.models import AuditMixin, ReminderMixin


class Event(AuditMixin, models.Model):
    EVENT_TYPE_CHOICES = [
        ("Zoom", "Zoom"),
        ("Virtual", "Virtual"),
        ("Phone", "Phone"),
        ("In-person", "In-person"),
    ]

    user = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True
    )
    # Who the event is for. Nobody means the firm: everyone's. An event may
    # be several people's (a hearing the attorney and the paralegal both
    # attend), so this is a set rather than one user.
    assignees = models.ManyToManyField(
        "accounts.CustomUser", blank=True, related_name="assigned_events"
    )
    matter = models.ForeignKey(Matter, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField(null=True)
    # Set only for an event over several days: its last day, inclusive. An
    # event on one day keeps this blank, so "is it multi-day" is one check.
    end_date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    party = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    event_type = models.CharField(
        max_length=50, choices=EVENT_TYPE_CHOICES, blank=True, null=True
    )
    # The place, as iCalendar's LOCATION: "courthouse & courtroom", an
    # address. A meeting's link is meeting_url, and its passcode and dial-in
    # numbers are in details.
    location = models.CharField(max_length=255, blank=True, null=True)
    # The link that joins a virtual meeting (Zoom, Teams, Meet, Webex): an
    # invitation's CONFERENCE, sent out as CONFERENCE and URL
    meeting_url = models.URLField(max_length=2000, blank=True, default="")
    # Free text, as iCalendar's DESCRIPTION and Google's description: what a
    # forwarded invitation says (passcode, meeting ID, dial-in numbers,
    # agenda), or anything the user writes
    details = models.TextField(blank=True, default="")
    # Who sent a forwarded invitation (its ORGANIZER), shown on the event;
    # blank for an event made in Kosmos, whose organizer is the firm
    organizer_name = models.CharField(max_length=255, blank=True, default="")
    organizer_email = models.EmailField(blank=True, default="")
    status = models.CharField(max_length=50, blank=True, null=True)
    # A calendar invitation forwarded in (apps.calendar.invitations): its
    # identifier, so a later revision of it updates this event and a
    # cancellation removes it, and its revision, so an older one is stale
    ical_uid = models.CharField(max_length=255, blank=True, default="")
    ical_sequence = models.IntegerField(default=0)
    # The invitations this event sends its guests: their identifier, set
    # when the first goes out, and their revision, raised with each change
    invite_uid = models.CharField(max_length=255, blank=True, default="")
    invite_sequence = models.IntegerField(default=0)
    history = HistoricalRecords(table_name="agenda_historicalevent")

    def __str__(self):
        return f"{self.description} : {self.id}"

    @property
    def ordered_assignees(self):
        """The assignees by name. Sorted here rather than in the query, so
        a feed that prefetched them makes no query per event."""
        return sorted(
            self.assignees.all(),
            key=lambda user: (user.first_name.lower(), user.last_name.lower(), user.id),
        )

    @property
    def assignee_initials(self):
        """The assignees' initials, "AL, JC", for the calendar's titles;
        empty for the firm's event."""
        return ", ".join(
            user.initials for user in self.ordered_assignees if user.initials
        )

    @property
    def assignee_names(self):
        """The assignees' short names, by name."""
        return [
            user.get_short_name() or user.username for user in self.ordered_assignees
        ]

    @property
    def calendar_title(self):
        """The event as the calendar names it: its matter, description and
        assignees' initials, dash-separated."""
        parts = [self.matter.name] if self.matter else []
        parts.append(self.description or "Untitled")
        if self.assignee_initials:
            parts.append(self.assignee_initials)
        return " - ".join(parts)

    @property
    def last_date(self):
        """The day the event ends: its end date, or its only day."""
        return self.end_date or self.date

    @property
    def start_at(self):
        """The moment a timed event starts, in the firm's zone; None for
        an all-day event or one with no date."""
        if not self.start_time or not self.date:
            return None
        return datetime.combine(
            self.date, self.start_time, tzinfo=timezone.get_default_timezone()
        )

    @property
    def end_at(self):
        """The moment a timed event ends; None without an end time."""
        if not self.end_time or not self.date:
            return None
        return datetime.combine(
            self.last_date, self.end_time, tzinfo=timezone.get_default_timezone()
        )

    class Meta:
        db_table = "app_event"
        indexes = [
            models.Index(fields=["matter"]),
        ]


class EventReminder(ReminderMixin):
    """A notification for an event (see ReminderMixin), to the user who
    added it: a firm's event may be on several people's calendars, and
    each sets their own."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="reminders")

    class Meta(ReminderMixin.Meta):
        db_table = "app_event_reminder"

    @property
    def target(self):
        return self.event

    @property
    def target_id(self):
        return self.event_id

    @property
    def target_start_at(self):
        return self.event.start_at

    @property
    def target_date(self):
        return self.event.date


class EventGuest(models.Model):
    """Someone outside the firm invited to an event (apps.calendar
    .invitations): their address, who invited them, and how they answered
    the invitation, if they have. People in the firm are assignees."""

    STATUS_CHOICES = [
        ("needs-action", "Invited"),
        ("accepted", "Yes"),
        ("tentative", "Maybe"),
        ("declined", "No"),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="guests")
    email = models.EmailField()
    name = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="needs-action"
    )
    invited_by = models.ForeignKey(
        "accounts.CustomUser", on_delete=models.SET_NULL, null=True, blank=True
    )
    invited_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_event_guest"
        ordering = ["invited_at"]
        constraints = [
            models.UniqueConstraint(fields=["event", "email"], name="guest_once")
        ]

    def __str__(self):
        return self.name or self.email
