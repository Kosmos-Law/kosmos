from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.crypto import salted_hmac
from simple_history.models import HistoricalRecords

from apps.accounts.managers import CustomUserManager

ROLE_OPTIONS = (
    ("ADMIN", "Admin"),
    ("USER", "User"),
)

NAV_LAYOUT_OPTIONS = (
    ("vertical", "Vertical"),
    ("horizontal", "Horizontal"),
)

# The icons a user may choose to stand for them in the sidebar's account
# menu (Lucide names), the plain person first, as the default. The same set
# as cpl's.
NAV_ICONS = [
    ("user", "Person"),
    ("chess-king", "King"),
    ("chess-queen", "Queen"),
    ("chess-rook", "Rook"),
    ("chess-bishop", "Bishop"),
    ("chess-knight", "Knight"),
    ("chess-pawn", "Pawn"),
    ("hamburger", "Hamburger"),
    ("toolbox", "Toolbox"),
    ("smile", "Smile"),
    ("laugh", "Laugh"),
    ("cat", "Cat"),
    ("dog", "Dog"),
    ("rabbit", "Rabbit"),
    ("squirrel", "Squirrel"),
    ("panda", "Panda"),
    ("turtle", "Turtle"),
    ("feather", "Feather"),
    ("bird", "Bird"),
    ("birdhouse", "Birdhouse"),
    ("rat", "Rat"),
    ("origami", "Origami"),
    ("rose", "Rose"),
    ("snail", "Snail"),
]


class CustomUser(AbstractUser):
    google_contacts_credentials = models.TextField(null=True, blank=True)
    google_calendar_credentials = models.TextField(null=True, blank=True)
    user_rate = models.IntegerField(default=0)
    initials = models.CharField(max_length=100, null=True, blank=True)
    role = models.CharField(max_length=5, choices=ROLE_OPTIONS, default="USER")
    nav_layout = models.CharField(
        max_length=20, choices=NAV_LAYOUT_OPTIONS, default="vertical"
    )
    # The icon that stands for the user in the sidebar, opening the account
    # menu (one of NAV_ICONS).
    nav_icon = models.CharField(max_length=40, choices=NAV_ICONS, default="user")
    # Bumped by Sign Out Everywhere (Settings > Security). It goes into the
    # hash every session is checked against, so each session made before
    # the bump stops matching and is signed out.
    sessions_ended = models.PositiveIntegerField(default=0)
    # User ids shown as one-click filter chips on the tasks toolbar (max
    # TASK_CHIPS_CAP, enforced at the toggle endpoint). Empty means "no
    # explicit picks": small firms show everyone, large ones fall back to
    # the overflow menu until the user pins a working set.
    task_user_chips = models.JSONField(default=list, blank=True)
    is_attorney = models.BooleanField(default=True)
    # Free-text job title ("Attorney", "Paralegal", "Office Manager", ...).
    # Shown in the users table and fed to the AI context so the model never
    # has to guess anyone's role. Blank falls back to the attorney flag.
    title = models.CharField(max_length=100, blank=True, default="")
    last_dash_check = models.DateField(null=True, blank=True)
    digest_enabled = models.BooleanField(default=False)
    digest_include_weekends = models.BooleanField(default=False)
    # Email this user when someone else adds an intake (Settings >
    # Notifications). Only reaches users who may see intakes.
    notify_new_intakes = models.BooleanField(default=False)
    perm_all_matters = models.BooleanField(default=True)
    perm_financial = models.BooleanField(default=True)
    perm_intakes = models.BooleanField(default=True)
    # Off until an administrator turns it on: the reports show the whole
    # firm's revenue, whatever matters or other permissions a user has.
    perm_reports = models.BooleanField(default=False)
    perm_research = models.BooleanField(default=True)
    history = HistoricalRecords()

    objects = CustomUserManager()

    PERM_FIELDS = (
        "perm_all_matters",
        "perm_financial",
        "perm_intakes",
        "perm_reports",
        "perm_research",
    )

    class Meta(AbstractUser.Meta):
        constraints = [
            # Users sign in with their email address, so it names one user
            # whatever its case. Blank is left out: the inactive system user
            # that signs notes from forwarded intake email has none.
            models.UniqueConstraint(
                Lower("email"),
                condition=~Q(email=""),
                name="accounts_customuser_email_unique",
            ),
        ]

    def _get_session_auth_hash(self, secret=None):
        # Django's own hash, with the sign-out-everywhere count mixed in
        # once there is one; at nought it is exactly Django's, so adding
        # it signed no one out.
        value = self.password
        if self.sessions_ended:
            value = f"{value}:{self.sessions_ended}"
        return salted_hmac(
            "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash",
            value,
            secret=secret,
            algorithm="sha256",
        ).hexdigest()

    @property
    def is_admin(self):
        return self.role == "ADMIN"

    @property
    def has_authenticator(self):
        return Authenticator.objects.filter(user_id=self.pk).exists()

    def has_matter_access(self, matter):
        if self.is_admin or self.perm_all_matters:
            return True
        return matter.members.filter(pk=self.pk).exists()

    @property
    def full_name(self):
        if not self.first_name or not self.last_name:
            return self.username.capitalize()

        return f"{self.first_name.capitalize()} {self.last_name.capitalize()}"

    @property
    def role_display(self):
        return dict(ROLE_OPTIONS)[self.role]

    @property
    def chip_initials(self):
        """Two-ish letter monogram for toolbar filter chips."""
        return (self.initials or self.username[:2]).upper()

    @property
    def title_display(self):
        """Job title for display and AI context; the attorney flag is the
        fallback when no explicit title has been set."""
        return self.title or ("Attorney" if self.is_attorney else "Staff")


class EmailVerificationCode(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    # Wrong guesses made against this code. Kept here, not in the session,
    # so the limit cannot be multiplied by opening more sessions.
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "app_accounts_email_verification_code"

    def is_expired(self):
        # total_seconds(), not .seconds: the latter wraps every 24 hours, so
        # an old code would read as fresh again once a day.
        return (timezone.now() - self.created_at).total_seconds() > 300  # 5 minutes


class Authenticator(models.Model):
    """A user's authenticator app (TOTP, RFC 6238). Once this row exists the
    app's code is the user's second sign-in step in place of the emailed
    code. The secret is stored as it is (apps/accounts/totp.py says why);
    its own row keeps it out of the user's history records."""

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="authenticator"
    )
    secret = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    # The 30-second step of the last code accepted. A code is good once:
    # a later attempt with the same step (a code read over a shoulder) is
    # refused even inside the clock-drift window.
    last_counter = models.BigIntegerField(default=0)

    class Meta:
        db_table = "app_accounts_authenticator"


# Wrong sign-ins allowed before the cooldown starts.
FREE_FAILURES = 5
# The first cooldown; each further failure doubles it, up to the cap.
COOLDOWN_BASE = timedelta(seconds=30)
COOLDOWN_CAP = timedelta(minutes=15)
# Failures this old are forgotten before a new one is counted.
FAILURE_MEMORY = timedelta(hours=1)


class SignInThrottle(models.Model):
    """Failed sign-ins per email address, as typed (lowercased), whether or
    not the address belongs to anyone: a cooldown that applied to real
    accounts alone would say which addresses exist. In the database, not
    the cache, so the count is the same whichever worker answers."""

    email = models.CharField(max_length=254, unique=True)
    failures = models.PositiveIntegerField(default=0)
    last_failure_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_accounts_sign_in_throttle"

    @staticmethod
    def key(email):
        return (email or "").strip().lower()[:254]

    @classmethod
    def cooldown_for(cls, failures):
        if failures < FREE_FAILURES:
            return timedelta(0)
        return min(COOLDOWN_BASE * 2 ** (failures - FREE_FAILURES), COOLDOWN_CAP)

    @classmethod
    def locked_until(cls, email):
        """When sign-in as ``email`` may be tried again, or None if now."""
        row = cls.objects.filter(email=cls.key(email)).first()
        if row is None or not row.last_failure_at:
            return None
        until = row.last_failure_at + cls.cooldown_for(row.failures)
        return until if until > timezone.now() else None

    @classmethod
    def record_failure(cls, email):
        now = timezone.now()
        row, _ = cls.objects.get_or_create(email=cls.key(email))
        if row.last_failure_at and now - row.last_failure_at > FAILURE_MEMORY:
            row.failures = 0
        row.failures += 1
        row.last_failure_at = now
        row.save()
        # Rows for addresses nobody has tried in a day say nothing: drop
        # them here rather than keep a job for it.
        cls.objects.filter(last_failure_at__lt=now - timedelta(days=1)).delete()

    @classmethod
    def clear(cls, email):
        cls.objects.filter(email=cls.key(email)).delete()
