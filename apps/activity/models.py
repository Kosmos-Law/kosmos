from django.db import models
from simple_history.models import HistoricalRecords

from utils.models import AuditMixin


class ActivityCategory(AuditMixin, models.Model):
    """A matter's coding buckets for activity — like accounting transaction
    codes, each entry lives in exactly one category (or none).

    Claimed categories become the sections of the matter's Fee Claim Report,
    ordered by position. Position is set by drag-reordering on the
    Categories tab, never edited directly.
    """

    name = models.CharField(max_length=100)
    matter = models.ForeignKey(
        "matters.Matter",
        on_delete=models.CASCADE,
        related_name="activity_categories",
    )
    claimed = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)
    history = HistoricalRecords()

    def __str__(self):
        return self.name

    class Meta:
        db_table = "app_activity_category"
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["matter", "name"],
                name="uniq_category_name_per_matter",
                violation_error_message="This matter already has a category with this name.",
            ),
        ]


# The entry models live in sub-packages. Importing them here registers
# them with the app registry as the app loads; nothing else does, now that
# there is no admin.py to import them at start-up. (Last, as they import
# ActivityCategory from this module.)
from apps.activity.expenses.models import ExpenseEntry  # noqa: E402, F401
from apps.activity.flat_fees.models import FlatFeeEntry  # noqa: E402, F401
from apps.activity.time.models import TimeEntry  # noqa: E402, F401
