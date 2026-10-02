import django_filters

from apps.intakes.models import Intake
from apps.matters.models import PracticeArea

INTAKE_STATUS_CHOICES = (
    ("Open", "Open"),
    ("Accepted", "Accepted"),
    ("Pending", "Pending"),
    ("Referred Out", "Referred Out"),
    ("Client Declined", "Client Declined"),
    ("Unresponsive", "Unresponsive"),
)

SOURCE_CHOICES = (
    ("Unknown", "Unknown"),
    ("Internet", "Internet"),
    ("Agent", "Agent"),
    ("Attorney - Internal", "Attorney - Internal"),
    ("Attorney - External", "Attorney - External"),
    ("Other", "Other"),
)


# The sorts the list offers: the column buttons and the Filter dialog's
# Order By. The order-by view accepts only these.
ORDER_FIELDS = ("date", "name", "importance")


class IntakeOrderingFilter(django_filters.OrderingFilter):
    """Sorts, then breaks ties newest first. Most intakes share one
    importance (Normal), so without a tie-break their order is the
    database's whim and rows can repeat or go missing between pages."""

    def filter(self, qs, value):
        if not value:
            return qs
        ordering = [self.get_ordering_value(param) for param in value]
        return qs.order_by(*ordering, "-date", "-id")


class IntakeFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=INTAKE_STATUS_CHOICES, empty_label="All"
    )
    practice_area = django_filters.ModelChoiceFilter(
        queryset=PracticeArea.objects.filter(is_active=True),
        empty_label="All",
    )
    date = django_filters.DateFromToRangeFilter(
        widget=django_filters.widgets.RangeWidget(attrs={"type": "date"})
    )
    source = django_filters.ChoiceFilter(choices=SOURCE_CHOICES, empty_label="All")
    order_by = IntakeOrderingFilter(
        fields=tuple((field, field) for field in ORDER_FIELDS),
        field_labels={
            "date": "Date",
            "name": "Name",
            "importance": "Importance",
        },
        empty_label=None,
    )

    class Meta:
        model = Intake
        fields = ["status", "practice_area", "date"]
