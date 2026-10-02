import django_filters
from django_filters.filters import forms

from apps.matters.models import Matter, PracticeArea

MATTER_STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("Open", "Open"),
    ("Closed", "Closed"),
    ("Complete", "Complete"),
)


class MatterFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=MATTER_STATUS_CHOICES, empty_label="All"
    )
    # The firm's own list (Settings, Practice Areas), inactive ones included
    # so matters filed under a retired area can still be found.
    practice_area = django_filters.ModelChoiceFilter(
        queryset=PracticeArea.objects.all(), empty_label="All"
    )
    date_start = django_filters.DateFilter(
        widget=forms.widgets.DateInput(attrs={"type": "date"}),
        field_name="date_start",
        lookup_expr="gte",
        label="Opened on or after",
    )
    date_end = django_filters.DateFilter(
        widget=forms.widgets.DateInput(attrs={"type": "date"}),
        field_name="date_end",
        lookup_expr="lte",
        label="Closed on or before",
    )
    order_by = django_filters.OrderingFilter(
        fields=(
            ("name", "name"),
            ("work_status", "work_status"),
            ("description", "description"),
        ),
        field_labels={
            "name": "Name",
            "work_status": "Work status",
            "description": "Description",
        },
        empty_label=None,
    )

    class Meta:
        model = Matter
        fields = [
            "status",
            "practice_area",
            "date_start",
            "date_end",
            "order_by",
        ]
