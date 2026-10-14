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
    assigned_to = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_events",
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
    # CharField (not TextField) on purpose: location is a short pointer — a
    # meeting link or "courthouse & courtroom" — not a notes field. 150 still
    # fits a Zoom URL + passcode.
    location = models.CharField(max_length=150, blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    google_id = models.CharField(max_length=255, blank=True, null=True)
    # When this event was last successfully pushed to Google Calendar. NULL means
    # never pushed. The push is needed whenever this is NULL or older than
    # updated_at (a local edit since the last sync) — that single comparison
    # drives create, update, first-connect backfill, and retry-after-failure.
    # One more state: synced once and now without a google_id. That is an
    # event removed on Google and kept here (see detached_from_google); it is
    # never pushed again.
    google_synced_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords(table_name="agenda_historicalevent")

    def __str__(self):
        return f"{self.description} : {self.id}"

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

    @property
    def detached_from_google(self):
        """True for an event that was deleted on Google and kept in Kosmos.

        The user took it off their calendar on purpose, so it must not go
        back as a new Google event. It is told apart from an event that was
        never pushed (no google_id, no google_synced_at) by still carrying
        the time of its last sync.
        """
        return not self.google_id and self.google_synced_at is not None

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


class CalendarSyncState(models.Model):
    """Stores Google Calendar sync token for incremental sync."""

    calendar_id = models.CharField(max_length=255, unique=True)
    sync_token = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_sync_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sync state for {self.calendar_id}"

    class Meta:
        db_table = "app_calendar_sync_state"


class PendingGoogleDeletion(models.Model):
    """A Google Calendar event that must be deleted remotely after a local
    delete whose push failed. The Event row is gone, so the marker can't live on
    it; reconcile() drains this and removes the record once Google confirms."""

    google_id = models.CharField(max_length=255, unique=True)
    calendar_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Pending deletion of {self.google_id}"

    class Meta:
        db_table = "app_calendar_pending_deletion"
