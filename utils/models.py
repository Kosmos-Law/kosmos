from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditMixin(models.Model):
    """
    Abstract mixin providing standard audit fields for tracking record
    creation and modification.

    Fields:
    - created_at: Timestamp when record was created
    - updated_at: Timestamp when record was last updated
    - created_by: User who created the record
    - updated_by: User who last updated the record

    User fields are automatically populated via CurrentUserMiddleware.
    """

    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        from utils.middleware import get_current_user

        user = get_current_user()
        if user and hasattr(user, "is_authenticated") and user.is_authenticated:
            if not self.pk and not self.created_by_id:
                self.created_by = user
            self.updated_by = user

        super().save(*args, **kwargs)


# How a notification reaches the user (utils.notify): by email, or pushed
# to the ntfy app on their phone. The user's choice in Settings is the
# default for new ones.
CHANNEL_CHOICES = (("email", "Email"), ("ntfy", "Push"))


class ReminderMixin(models.Model):
    """A notification for something with a date: an event, a task.

    Attributes:
        user: who it reaches
        channel (str): how it reaches them (CHANNEL_CHOICES)
        amount (int): how many of the unit before the thing
        unit (str): minutes, hours, days or weeks
        time (time): for a thing with no time of its own, the time of day
            the notification goes out; ignored when there is a time to
            count back from
        sent_for (datetime): the moment the notification was last sent
            for. It is compared with the moment it is now due, so a thing
            that moves is notified again, and one that does not is
            notified once.

    A subclass names what it is for: ``target`` (the thing),
    ``target_start_at`` (its moment, or None when it has no time) and
    ``target_date`` (its day, or None when it has none).
    """

    UNIT_CHOICES = [
        ("minutes", "minutes"),
        ("hours", "hours"),
        ("days", "days"),
        ("weeks", "weeks"),
    ]
    ALL_DAY_UNITS = ("days", "weeks")
    DEFAULT_TIME = time(9, 0)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="email")
    amount = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="minutes")
    time = models.TimeField(null=True, blank=True)
    sent_for = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ["-unit", "-amount"]

    def __str__(self):
        return f"{self.describe()} : {self.target_id}"

    @property
    def offset(self):
        return timedelta(**{self.unit: self.amount})

    @property
    def timed(self):
        return self.target_start_at is not None

    @property
    def fire_at(self):
        """When the notification goes out, or None when the thing has no
        date yet.

        Something with a time counts back from that moment. Something with
        only a day counts back whole days and goes out at the
        notification's time of day, in the firm's zone.
        """
        start = self.target_start_at
        if start is not None:
            return start - self.offset
        day = self.target_date
        if day is None:
            return None
        moment = datetime.combine(
            day,
            self.time or self.DEFAULT_TIME,
            tzinfo=timezone.get_default_timezone(),
        )
        return moment - self.offset

    def describe(self):
        """The notification in words: "30 minutes before", "1 day before
        at 9:00 AM", "At the start", "That day at 9:00 AM"."""
        at = ""
        if not self.timed:
            at = " at " + (self.time or self.DEFAULT_TIME).strftime("%-I:%M %p")
        if self.amount == 0:
            return ("That day" + at) if at else "At the start"
        unit = self.unit if self.amount != 1 else self.unit[:-1]
        return f"{self.amount} {unit} before{at}"
